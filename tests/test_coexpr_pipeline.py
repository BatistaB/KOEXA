"""Tests for aoryzae_atlas.coexpr.pipeline: depth filter, both modes, outputs, enrichment, refusal on too little data."""
from __future__ import annotations

import json

import duckdb
import numpy as np
import pandas as pd
import pytest

from aoryzae_atlas.coexpr.network import CoexprParams
from aoryzae_atlas.coexpr.pipeline import (
    CoexpressionNotPossibleError,
    build_coexpression,
    write_coexpression_outputs,
)
from aoryzae_atlas.database.migrate import apply_migrations

LAYOUT = [("PRJA", "RIB40", 18, 3e7), ("PRJB", "RIB40", 18, 2e7), ("PRJC", "ENG", 14, 1.2e7), ("PRJD", "ENG", 10, 4e6)]
MODULE = [f"M0_{k:02d}" for k in range(10)]


def _seed(conn) -> None:
    """4 studies; PRJD is shallow (4M assigned reads). One module of 10 genes shares a latent factor; every gene has study offsets."""
    rng = np.random.default_rng(0)
    samples, qc = [], []
    for study, strain, n, depth in LAYOUT:
        for i in range(n):
            run = f"{study}_R{i}"
            samples.append((run, run, f"{study}_BS{i}", study, strain, "QUANTIFIED"))
            qc.append((run, "salmon_total_gene_assigned_counts", depth * rng.uniform(0.9, 1.1)))
    samples_df = pd.DataFrame(samples, columns=["sample_id", "run_accession", "biosample", "bioproject", "strain", "pipeline_status"])
    conn.register("samples_df", samples_df)
    conn.execute("INSERT INTO samples (sample_id, run_accession, biosample, bioproject, strain, pipeline_status) SELECT * FROM samples_df")
    qc_df = pd.DataFrame(qc, columns=["sample_id", "metric_name", "metric_value"])
    conn.register("qc_df", qc_df)
    conn.execute("INSERT INTO sample_qc (sample_id, metric_name, metric_value) SELECT * FROM qc_df")

    runs = samples_df["sample_id"].tolist()
    study = samples_df["bioproject"].to_numpy()
    genes = MODULE + [f"N{k:03d}" for k in range(90)] + ["LOW000"]
    factor = rng.normal(size=len(runs))
    log = np.zeros((len(genes), len(runs)))
    for gi, gene in enumerate(genes):
        offsets = {s: rng.normal(0, 1.2) for s in set(study)}
        log[gi] = 4.0 + np.array([offsets[s] for s in study]) + rng.normal(0, 0.5, len(runs))
        if gene in MODULE:
            log[gi] += 1.2 * factor
    tpm = 2.0 ** log
    tpm[-1] = 0.01                                           # LOW000: mean TPM < 1 -> not in the network
    genes_df = pd.DataFrame({"canonical_gene_id": genes, "gene_symbol": "", "description": [f"desc {g}" for g in genes]})
    conn.register("genes_df", genes_df)
    conn.execute("INSERT INTO genes (canonical_gene_id, gene_symbol, description) SELECT * FROM genes_df")
    expr_df = pd.DataFrame({
        "sample_id": np.tile(runs, len(genes)), "canonical_gene_id": np.repeat(genes, len(runs)),
        "TPM": tpm.ravel(), "estimated_counts": tpm.ravel() * 10, "effective_length": np.nan,
    })
    conn.register("expr_df", expr_df)
    conn.execute("INSERT INTO gene_expression (sample_id, canonical_gene_id, TPM, estimated_counts, effective_length) SELECT * FROM expr_df")


@pytest.fixture(scope="module")
def seeded(tmp_path_factory):
    path = tmp_path_factory.mktemp("coexpr_db") / "seeded.duckdb"
    apply_migrations(path)
    conn = duckdb.connect(str(path))
    _seed(conn)
    yield conn
    conn.close()


@pytest.fixture(scope="module")
def gaf(tmp_path_factory):
    """GO annotations: MODULE genes carry the 'translation' term (a benchmark group), noise genes unrelated terms."""
    rng = np.random.default_rng(1)
    path = tmp_path_factory.mktemp("gaf") / "mini.gaf"
    noise = [f"N{k:03d}" for k in range(90)]
    lines = ["!gaf-version: 2.2"]
    for g in MODULE:
        lines.append(f"FungiDB\t{g}\tsym\t\tGO:0006412\tref\tIEA\t\tP\t\t\tgene\ttaxon:5062\t20200101\tFungiDB")
    for t in range(6):
        for g in rng.choice(noise, 12, replace=False):
            lines.append(f"FungiDB\t{g}\tsym\t\tGO:020000{t}\tref\tIEA\t\tP\t\t\tgene\ttaxon:5062\t20200101\tFungiDB")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


PARAMS = CoexprParams(min_assigned_reads=1e7, top_n=9, min_samples=20, null_pairs=20_000)


def test_depth_filter_selects_deep_biosamples_and_fixes_gene_universe(seeded):
    result = build_coexpression(seeded, PARAMS)
    scope = result.scope
    assert scope["n_biosamples_total"] == 60 and scope["n_biosamples_selected"] == 50      # PRJD (10 shallow) dropped
    assert scope["n_studies_selected"] == 3 and scope["n_biosamples_unknown_depth"] == 0
    assert scope["n_genes"] == 100                                                          # 10 module + 90 noise; LOW000 filtered
    assert set(result.modes) == {"all_samples", "within_study"}
    assert result.modes["all_samples"].prepared.n_samples == 50
    assert set(result.modes["all_samples"].prepared.genes) == set(result.modes["within_study"].prepared.genes)
    assert {r["min_assigned_reads_M"]: r["biosamples"] for r in scope["depth_table"]}[0] == 60


def test_cutoff_zero_keeps_every_biosample(seeded):
    result = build_coexpression(seeded, CoexprParams(min_assigned_reads=0, top_n=5, min_samples=20, null_pairs=5000))
    assert result.scope["n_biosamples_selected"] == 60 and result.scope["n_studies_selected"] == 4


def test_module_is_found_and_edges_carry_support_columns(seeded):
    result = build_coexpression(seeded, PARAMS)
    table = result.modes["within_study"].neighbours
    assert len(table) == 100 * 9
    for col in ("gene_id", "neighbour_id", "rank", "r", "reverse_rank", "mutual_rank", "bg_tail", "within_study_median_r", "n_studies_tested"):
        assert col in table.columns
    gene = table[table["gene_id"] == MODULE[0]]
    assert set(gene["neighbour_id"]) == set(MODULE) - {MODULE[0]}
    assert (gene["within_study_median_r"] > 0.5).all() and (gene["n_studies_tested"] == 3).all()
    assert gene["mutual_rank"].max() <= 9 + 1e-6                                      # module members rank each other within the module
    combined = result.neighbours()
    assert set(combined["mode"]) == {"all_samples", "within_study"} and len(combined) == 2 * len(table)


def test_pipeline_is_deterministic(seeded):
    a = build_coexpression(seeded, PARAMS).neighbours()
    b = build_coexpression(seeded, PARAMS).neighbours()
    pd.testing.assert_frame_equal(a, b)


def test_too_few_deep_biosamples_is_refused_not_guessed(seeded):
    with pytest.raises(CoexpressionNotPossibleError, match="biosample"):
        build_coexpression(seeded, CoexprParams(min_assigned_reads=1e9, min_samples=20))


def test_empty_database_is_refused(tmp_path):
    path = tmp_path / "empty.duckdb"
    apply_migrations(path)
    conn = duckdb.connect(str(path))
    try:
        with pytest.raises(CoexpressionNotPossibleError, match="QUANTIFIED"):
            build_coexpression(conn)
    finally:
        conn.close()


def test_within_study_mode_is_skipped_when_per_study_filter_leaves_too_little(seeded):
    # 3 studies pass the depth filter; asking for >= 19 biosamples per study leaves only PRJA/PRJB-sized studies out
    params = CoexprParams(min_assigned_reads=1e7, top_n=5, min_samples=20, min_samples_per_study=19, null_pairs=5000)
    result = build_coexpression(seeded, params)
    assert "within_study" in result.scope["skipped_modes"] and "all_samples" in result.modes


def test_enrichment_with_go_annotations(seeded, gaf):
    result = build_coexpression(seeded, PARAMS, gaf_path=gaf)
    assert result.scope["go"]["n_terms"] >= 1 and "direct" in result.scope["go"]["source"]
    enrichment = result.modes["within_study"].enrichment
    module_hits = enrichment[(enrichment["gene_id"].isin(MODULE)) & (enrichment["term"] == "GO:0006412")]
    assert set(module_hits["gene_id"]) == set(MODULE) and (module_hits["q_value"] <= 0.05).all()
    bench = result.benchmark().set_index(["mode", "group"])
    assert bench.loc[("within_study", "translation_ribosome"), "auc"] > 0.9      # the planted module is the 'translation' group


def test_without_gaf_there_is_no_enrichment_but_the_network_still_builds(seeded):
    result = build_coexpression(seeded, PARAMS, gaf_path=None)
    assert result.scope["go"] is None and result.enrichment().empty
    assert not result.neighbours().empty


def test_write_outputs_strict_json_and_stale_enrichment_removed(seeded, gaf, tmp_path):
    paths = dict(
        neighbours_path=tmp_path / "nb.parquet", enrichment_path=tmp_path / "enr.parquet",
        benchmark_path=tmp_path / "bench.tsv", summary_path=tmp_path / "summary.json", profiles_dir=tmp_path / "profiles",
    )
    write_coexpression_outputs(build_coexpression(seeded, PARAMS, gaf_path=gaf), **paths)
    assert paths["enrichment_path"].exists()
    summary = json.loads(paths["summary_path"].read_text(encoding="utf-8"))       # strict JSON: no NaN literals
    assert summary["n_biosamples_selected"] == 50 and set(summary["modes"]) == {"all_samples", "within_study"}
    nb = pd.read_parquet(paths["neighbours_path"])
    assert len(nb) == 2 * 100 * 9
    profiles = pd.read_parquet(paths["profiles_dir"] / "zscores_within_study.parquet")
    assert profiles.shape == (100, 50)
    assert pd.read_csv(paths["benchmark_path"], sep="\t").shape[0] >= 1

    write_coexpression_outputs(build_coexpression(seeded, PARAMS, gaf_path=None), **paths)
    assert not paths["enrichment_path"].exists()
