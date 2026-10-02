"""Tests for aoryzae_atlas.rank.pipeline and the expression_rank web export."""
from __future__ import annotations

import json

import duckdb
import numpy as np
import pandas as pd
import pytest

from aoryzae_atlas.database.migrate import apply_migrations
from aoryzae_atlas.rank import pipeline as rank_pipeline
from aoryzae_atlas.rank.classes import CLASS_ORDER
from aoryzae_atlas.rank.pipeline import (
    SPEC_COLUMNS,
    NoQuantifiedSamplesError,
    build_expression_rank,
    write_rank_outputs,
)
from aoryzae_atlas.webexport import build as webexport


@pytest.fixture
def conn(tmp_path):
    db_path = tmp_path / "rank.duckdb"
    apply_migrations(db_path)
    connection = duckdb.connect(str(db_path))
    yield connection
    connection.close()


def _seed(conn, n_genes: int = 160, seed: int = 0) -> list[str]:
    """3 studies x 2 strains; one biosample is re-sequenced (2 runs). Bulk-inserts (executemany is far too slow)."""
    rng = np.random.default_rng(seed)
    layout = [("PRJA", "RIB40", 20), ("PRJB", "RIB40", 16), ("PRJC", "ENG", 12)]
    samples = []
    for study, strain, n in layout:
        for i in range(n):
            biosample = f"{study}_BS{i}"
            runs = [f"{study}_R{i}"] + ([f"{study}_R{i}b"] if (study, i) == ("PRJA", 0) else [])
            samples += [(run, run, biosample, study, strain, "QUANTIFIED") for run in runs]
    samples_df = pd.DataFrame(samples, columns=["sample_id", "run_accession", "biosample", "bioproject", "strain", "pipeline_status"])
    conn.register("samples_df", samples_df)
    conn.execute("INSERT INTO samples (sample_id, run_accession, biosample, bioproject, strain, pipeline_status) SELECT * FROM samples_df")

    gene_ids = [f"G{i:04d}" for i in range(n_genes)]
    genes_df = pd.DataFrame({
        "canonical_gene_id": gene_ids,
        "gene_symbol": [f"sym{i}" if i % 10 == 0 else "" for i in range(n_genes)],
        "description": [f"desc {g}" for g in gene_ids],
    })
    conn.register("genes_df", genes_df)
    conn.execute("INSERT INTO genes (canonical_gene_id, gene_symbol, description) SELECT * FROM genes_df")

    runs = samples_df["sample_id"].tolist()
    kind = np.arange(n_genes) % 4
    tpm = np.zeros((n_genes, len(runs)))
    for gi in range(n_genes):
        if kind[gi] == 0:
            tpm[gi] = np.exp(rng.normal(6.0, 0.15, len(runs)))
        elif kind[gi] == 1:
            tpm[gi] = np.exp(rng.normal(3.0, 0.2, len(runs)))
        elif kind[gi] == 2:
            on = rng.random(len(runs)) < 0.08
            tpm[gi] = np.where(on, rng.uniform(0, 300, len(runs)), 0.0)
        else:
            tpm[gi] = rng.uniform(0, 0.02, len(runs))
    expr_df = pd.DataFrame({
        "sample_id": np.tile(runs, n_genes),
        "canonical_gene_id": np.repeat(gene_ids, len(runs)),
        "TPM": tpm.ravel(),
        "estimated_counts": tpm.ravel() * 10,
        "effective_length": np.nan,
    })
    conn.register("expr_df", expr_df)
    conn.execute("INSERT INTO gene_expression (sample_id, canonical_gene_id, TPM, estimated_counts, effective_length) SELECT * FROM expr_df")
    return gene_ids


@pytest.fixture(scope="module")
def seeded(tmp_path_factory):
    db_path = tmp_path_factory.mktemp("rank_db") / "seeded.duckdb"
    apply_migrations(db_path)
    connection = duckdb.connect(str(db_path))
    gene_ids = _seed(connection)
    yield connection, gene_ids
    connection.close()


def test_build_expression_rank_end_to_end(seeded):
    conn, gene_ids = seeded
    result = build_expression_rank(conn)
    final = result.final

    assert list(final.index) == sorted(gene_ids) and final.index.name == "gene_id"
    for col in SPEC_COLUMNS:
        assert col in final.columns
    assert set(final["expression_class"]) <= set(CLASS_ORDER)
    # 3 studies; 48 biosamples out of 49 runs (one biosample re-sequenced)
    assert result.scope["n_samples"] == 48 and result.scope["n_runs"] == 49
    assert result.scope["n_studies"] == 3 and result.scope["n_strains"] == 2
    assert sum(result.scope["class_counts"].values()) == len(gene_ids)
    assert final["gene_symbol"].notna().all()


def test_technical_replicates_are_one_independent_sample(seeded):
    conn, _ = seeded
    result = build_expression_rank(conn)
    assert result.tpm.shape[1] == 48
    assert "PRJA|PRJA_BS0" in result.tpm.columns  # both runs of that biosample live in one column


def test_robustness_is_leave_one_study_and_strain_out(seeded):
    conn, _ = seeded
    result = build_expression_rank(conn)
    labels = set(result.robustness["perturbation"])
    assert {"leave out study PRJA", "leave out study PRJB", "leave out study PRJC"} <= labels
    assert "leave out strain ENG" in labels
    # leaving out RIB40 would leave only 12 independent samples (< the 20-sample guard): skipped, not run
    assert "leave out strain RIB40" not in labels
    assert result.robustness["class_agreement"].between(0, 1).all()


def test_without_robustness_skips_the_reruns(seeded):
    conn, _ = seeded
    result = build_expression_rank(conn, with_robustness=False)
    assert result.robustness.empty and result.scope["median_robustness_agreement"] is None


def test_empty_database_raises(conn):
    with pytest.raises(NoQuantifiedSamplesError):
        build_expression_rank(conn)


def test_pipeline_is_deterministic(seeded):
    conn, _ = seeded
    a = build_expression_rank(conn, with_robustness=False).final
    b = build_expression_rank(conn, with_robustness=False).final
    pd.testing.assert_frame_equal(a, b)


def test_write_outputs_and_strict_json(seeded, tmp_path):
    conn, _ = seeded
    result = build_expression_rank(conn)
    paths = {k: tmp_path / v for k, v in {
        "parquet_path": "rank.parquet", "tsv_gz_path": "rank.tsv.gz", "thresholds_path": "thr.tsv",
        "summary_path": "summary.json", "biosample_matrix_path": "tpm.parquet",
    }.items()}
    write_rank_outputs(result, **paths)
    table = pd.read_parquet(paths["parquet_path"])
    assert len(table) == len(result.final) and "gene_id" in table.columns
    summary = json.loads(paths["summary_path"].read_text(encoding="utf-8"))  # strict JSON: no NaN literals
    assert summary["n_genes"] == len(table) and summary["class_order"] == list(CLASS_ORDER)
    assert pd.read_csv(paths["thresholds_path"], sep="\t").shape[0] >= 8
    assert pd.read_parquet(paths["biosample_matrix_path"]).shape[1] == 48


def test_export_expression_rank_roundtrip(seeded, tmp_path, monkeypatch):
    conn, _ = seeded
    result = build_expression_rank(conn)
    parquet, summary_path = tmp_path / "rank.parquet", tmp_path / "summary.json"
    write_rank_outputs(result, parquet, tmp_path / "r.tsv.gz", tmp_path / "t.tsv", summary_path)
    monkeypatch.setattr(webexport, "EXPRESSION_RANK_FILE", parquet)
    monkeypatch.setattr(webexport, "EXPRESSION_RANK_SUMMARY_FILE", summary_path)

    payload = webexport.export_expression_rank()
    assert payload is not None and payload["columns"][0] == "gene_id"
    assert len(payload["rows"]) == len(result.final)
    assert payload["summary"]["n_samples"] == 48
    json.dumps(payload, allow_nan=False)  # strict JSON for the browser
    class_idx = payload["columns"].index("expression_class")
    assert {row[class_idx] for row in payload["rows"]} <= set(CLASS_ORDER)


def test_export_expression_rank_none_when_not_run(tmp_path, monkeypatch):
    monkeypatch.setattr(webexport, "EXPRESSION_RANK_FILE", tmp_path / "missing.parquet")
    assert webexport.export_expression_rank() is None


def test_pipeline_version_constant_exists():
    assert isinstance(rank_pipeline.RANK_PIPELINE_VERSION, str)
