"""Tests for aoryzae_atlas.coexpr.network and aoryzae_atlas.coexpr.enrichment (pure functions, no database)."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest
from scipy.stats import false_discovery_control, fisher_exact, rankdata

from aoryzae_atlas.coexpr.enrichment import (
    bh_adjust,
    build_term_sets,
    enrich_gene_set,
    load_go_obo,
    neighbourhood_enrichment,
    propagate_annotations,
)
from aoryzae_atlas.coexpr.network import (
    CoexprParams,
    coexpressed_with_set,
    correlation_null,
    depth_scope_table,
    functional_benchmark,
    neighbour_table,
    prepare_expression,
    select_biosamples,
    select_edges,
    study_consistency,
    top_neighbours,
)

PARAMS = CoexprParams(min_samples=10, min_samples_per_study=3, null_pairs=20_000)


def _synthetic(n_per_study: int = 20, n_studies: int = 4, module_size: int = 8, n_noise: int = 60, seed: int = 0):
    """Genes x biosamples TPM with two real modules (shared latent factor) and strong study offsets for every gene.

    Returns (tpm, study_of, modules). Study offsets are independent per gene, so noise genes correlate across
    the pooled data only through them -- exactly the artefact within_study mode must remove.
    """
    rng = np.random.default_rng(seed)
    n = n_per_study * n_studies
    study = np.repeat([f"PRJ{k}" for k in range(n_studies)], n_per_study)
    samples = [f"{s}|BS{i}" for i, s in enumerate(study)]
    modules = {m: [f"M{m}_{k}" for k in range(module_size)] for m in range(2)}
    noise = [f"N{k}" for k in range(n_noise)]
    genes = [g for gs in modules.values() for g in gs] + noise
    factors = {m: rng.normal(size=n) for m in modules}
    log = np.zeros((len(genes), n))
    for gi, gene in enumerate(genes):
        offsets = dict(zip(sorted(set(study)), rng.normal(0, 1.5, n_studies)))
        log[gi] = 4.0 + np.array([offsets[s] for s in study]) + rng.normal(0, 0.5, n)
        for m, members in modules.items():
            if gene in members:
                log[gi] += 1.2 * factors[m]
    tpm = pd.DataFrame(2.0 ** log, index=genes, columns=samples)
    return tpm, pd.Series(study, index=samples), modules


def test_params_validation():
    with pytest.raises(ValueError):
        CoexprParams(method="kendall")
    with pytest.raises(ValueError):
        CoexprParams(top_n=0)
    with pytest.raises(ValueError):
        CoexprParams(min_samples_per_study=2)


def test_select_biosamples_unknown_depth_never_passes():
    depth = pd.Series([2e7, 5e6, np.nan, 1e7], index=list("abcd"))
    assert list(select_biosamples(depth, 1e7)) == ["a", "d"]       # >= is inclusive; NaN excluded
    assert list(select_biosamples(depth, 0)) == list("abcd")        # no filter keeps everything, NaN included


def test_depth_scope_table_counts_studies_and_strains():
    depth = pd.Series([3e7, 1e7, 2e6], index=["a", "b", "c"])
    meta = pd.DataFrame({"bioproject": ["P1", "P1", "P2"], "strain": ["S1", "S2", "S1"]}, index=depth.index)
    table = depth_scope_table(depth, meta, cutoffs_millions=(0, 10, 20)).set_index("min_assigned_reads_M")
    assert list(table["biosamples"]) == [3, 2, 1]
    assert list(table["studies"]) == [2, 1, 1] and list(table["strains"]) == [2, 2, 1]


@pytest.mark.parametrize("method", ["pearson", "spearman"])
def test_profiles_are_standardized(method):
    tpm, study, _ = _synthetic()
    for mode in ("all_samples", "within_study"):
        prepared = prepare_expression(tpm, study, mode, CoexprParams(method=method, min_samples=10))
        assert np.allclose(prepared.z.mean(axis=1), 0, atol=1e-5)
        assert np.allclose(prepared.z.std(axis=1), 1, atol=1e-4)


def test_spearman_is_invariant_to_monotone_transforms():
    tpm, study, _ = _synthetic()
    base = prepare_expression(tpm, study, "all_samples", CoexprParams(method="spearman"), genes=tpm.index)
    # log2(TPM+1) is monotone in TPM: ranks (hence z) must not change under any further monotone map of it
    squashed = prepare_expression(np.sqrt(tpm), study, "all_samples", CoexprParams(method="spearman"), genes=tpm.index)
    assert np.allclose(base.z, squashed.z, atol=1e-5)


def test_zero_variance_gene_gets_zero_correlations_not_nan():
    tpm, study, _ = _synthetic()
    tpm.loc["CONST"] = 5.0
    prepared = prepare_expression(tpm, study, "all_samples", PARAMS, genes=tpm.index)
    nb = top_neighbours(prepared.z, 5)
    assert np.isfinite(nb.r).all() and (nb.r[list(prepared.genes).index("CONST")] == 0).all()


def test_within_study_mode_drops_small_studies():
    tpm, study, _ = _synthetic()
    study = study.copy()
    study.iloc[:2] = "TINY"                       # 2 biosamples < min_samples_per_study
    prepared = prepare_expression(tpm, study, "within_study", PARAMS, genes=tpm.index)
    assert prepared.n_samples == tpm.shape[1] - 2 and "TINY" not in set(prepared.study_of)
    assert prepare_expression(tpm, study, "all_samples", PARAMS, genes=tpm.index).n_samples == tpm.shape[1]


def test_modules_are_recovered_as_top_neighbours():
    tpm, study, modules = _synthetic()
    prepared = prepare_expression(tpm, study, "within_study", PARAMS, genes=tpm.index)
    nb = top_neighbours(prepared.z, top_n=7)
    genes = list(prepared.genes)
    for members in modules.values():
        for gene in members:
            found = {genes[j] for j in nb.idx[genes.index(gene)]}
            assert found == set(members) - {gene}


def test_study_offsets_fake_correlation_in_pooled_mode_but_not_within_study():
    tpm, study, _ = _synthetic()
    noise = [g for g in tpm.index if g.startswith("N")]
    pooled = prepare_expression(tpm, study, "all_samples", PARAMS, genes=tpm.index)
    within = prepare_expression(tpm, study, "within_study", PARAMS, genes=tpm.index)
    frac = lambda z: (np.abs(correlation_null(z[[list(tpm.index).index(g) for g in noise]], 20_000, 0)) >= 0.5).mean()
    assert frac(pooled.z) > 0.15            # independent genes look co-expressed through the study offsets
    assert frac(within.z) < 0.05            # and stop once each study is centered


def test_neighbour_table_ranks_and_mutual_rank_against_brute_force():
    rng = np.random.default_rng(3)
    z = rng.normal(size=(40, 25))
    z = (z - z.mean(1, keepdims=True)) / z.std(1, keepdims=True)
    genes = pd.Index([f"G{i}" for i in range(40)])
    nb = top_neighbours(z, top_n=6, block_size=16)                 # several blocks on purpose
    r = z @ z.T / z.shape[1]
    np.fill_diagonal(r, -np.inf)
    order = np.argsort(-r, axis=1, kind="stable")
    full_rank = np.empty_like(order)
    for i in range(40):
        full_rank[i, order[i]] = np.arange(1, 41)
    assert (nb.idx == order[:, :6]).all()
    expected_reverse = np.array([[full_rank[j, i] for j in nb.idx[i]] for i in range(40)])
    assert (nb.reverse_rank == expected_reverse).all()

    table = neighbour_table(genes, nb, np.sort(rng.normal(size=1000) * 0.2))
    assert len(table) == 40 * 6 and list(table["rank"][:6]) == [1, 2, 3, 4, 5, 6]
    assert not (table["gene_id"] == table["neighbour_id"]).any()
    assert (table["r"].diff().dropna()[table["rank"][1:] > 1] <= 1e-6).all()    # r non-increasing down each list
    # mutual rank is symmetric: when both directions are listed they agree
    key = {(a, b): m for a, b, m in zip(table["gene_id"], table["neighbour_id"], table["mutual_rank"])}
    both = [(a, b) for (a, b) in key if (b, a) in key]
    assert both and all(key[(a, b)] == pytest.approx(key[(b, a)]) for a, b in both)


def test_bg_tail_decreases_with_r():
    z = np.random.default_rng(0).normal(size=(60, 30))
    z = (z - z.mean(1, keepdims=True)) / z.std(1, keepdims=True)
    null = correlation_null(z, 5000, 0)
    nb = top_neighbours(z, 5)
    table = neighbour_table(pd.Index([f"G{i}" for i in range(60)]), nb, null)
    ordered = table.sort_values("r")
    assert (ordered["bg_tail"].diff().dropna() <= 1e-9).all()
    assert table["bg_tail"].between(0, 1).all()


def test_study_consistency_separates_real_from_study_driven_edges():
    tpm, study, modules = _synthetic()
    prepared = prepare_expression(tpm, study, "all_samples", PARAMS, genes=tpm.index)
    genes = list(prepared.genes)
    real = (genes.index(modules[0][0]), genes.index(modules[0][1]))
    noise = [genes.index(g) for g in genes if g.startswith("N")]
    # a noise pair that looks correlated in the pooled data purely via study offsets
    pooled_r = prepared.z[noise] @ prepared.z[noise].T / prepared.z.shape[1]
    np.fill_diagonal(pooled_r, 0)
    a, b = np.unravel_index(np.argmax(pooled_r), pooled_r.shape)
    fake = (noise[a], noise[b])
    support, n_tested = study_consistency(prepared, np.array([real[0], fake[0]]), np.array([real[1], fake[1]]), PARAMS)
    assert pooled_r[a, b] > 0.5
    assert support[0] > 0.5 and support[1] < support[0] - 0.3
    assert (n_tested == 4).all()


def test_functional_benchmark_flags_a_real_module_and_not_a_random_set():
    tpm, study, modules = _synthetic()
    prepared = prepare_expression(tpm, study, "within_study", PARAMS, genes=tpm.index)
    null = correlation_null(prepared.z, 20_000, 0)
    rng = np.random.default_rng(1)
    sets = pd.DataFrame(False, index=prepared.genes, columns=["module", "random"])
    sets.loc[modules[0], "module"] = True
    sets.loc[rng.choice([g for g in prepared.genes if g.startswith("N")], 20, replace=False), "random"] = True
    bench = functional_benchmark(prepared.z, prepared.genes, sets, null, n_pairs=3000, min_genes=5).set_index("group")
    assert bench.loc["module", "auc"] > 0.95
    assert abs(bench.loc["random", "auc"] - 0.5) < 0.1
    # groups below min_genes are skipped, not reported with a meaningless AUC
    assert "module" not in functional_benchmark(prepared.z, prepared.genes, sets, null, min_genes=50)["group"].tolist()


def test_coexpressed_with_set():
    tpm, study, modules = _synthetic()
    prepared = prepare_expression(tpm, study, "within_study", PARAMS, genes=tpm.index)
    members = modules[1][:3]
    hits = coexpressed_with_set(prepared.z, prepared.genes, members, top_n=5)
    assert set(hits["gene_id"]) == set(modules[1]) - set(members)     # members excluded, the rest of the module found
    assert (hits["mean_r"].diff().dropna() <= 0).all() and (hits["min_r"] <= hits["mean_r"] + 1e-9).all()
    single = coexpressed_with_set(prepared.z, prepared.genes, [modules[0][0]], top_n=1)
    nb = top_neighbours(prepared.z, 1)
    assert single["gene_id"].iloc[0] == prepared.genes[nb.idx[list(prepared.genes).index(modules[0][0]), 0]]
    with pytest.raises(KeyError):
        coexpressed_with_set(prepared.z, prepared.genes, ["NOPE"])


# --- enrichment -------------------------------------------------------------------------------------------

def test_bh_adjust_matches_scipy_and_accounts_for_untested_hypotheses():
    p = np.array([0.01, 0.04, 0.03, 0.005, 0.2])
    assert np.allclose(bh_adjust(p), false_discovery_control(p, method="bh"))
    padded = np.concatenate([p, np.ones(5)])
    assert np.allclose(bh_adjust(p, n_tests=10), false_discovery_control(padded, method="bh")[:5])


OBO = """format-version: 1.2

[Term]
id: GO:0000001
name: root process
namespace: biological_process

[Term]
id: GO:0000002
name: child process
namespace: biological_process
alt_id: GO:0000009
is_a: GO:0000001 ! root process

[Term]
id: GO:0000003
name: part of child
namespace: biological_process
relationship: part_of GO:0000002 ! child process

[Term]
id: GO:0000004
name: old thing
is_obsolete: true

[Typedef]
id: part_of
name: part of
"""


def test_obo_parsing_and_propagation(tmp_path):
    path = tmp_path / "mini.obo"
    path.write_text(OBO, encoding="utf-8")
    onto = load_go_obo(path)
    assert onto.names["GO:0000002"] == "child process" and onto.alt_ids["GO:0000009"] == "GO:0000002"
    assert onto.obsolete == {"GO:0000004"} and onto.parents["GO:0000003"] == {"GO:0000002"}
    go = pd.DataFrame({"gene": ["g1", "g2", "g3"], "go_id": ["GO:0000003", "GO:0000009", "GO:0000004"]})
    expanded = propagate_annotations(go, onto)
    got = {g: set(x["go_id"]) for g, x in expanded.groupby("gene")}
    assert got["g1"] == {"GO:0000003", "GO:0000002", "GO:0000001"}       # part_of and is_a followed
    assert got["g2"] == {"GO:0000002", "GO:0000001"}                      # alt id mapped to the primary id
    assert "g3" not in got                                                # obsolete annotation dropped


def _annotation_universe(n_genes: int = 300, seed: int = 0):
    rng = np.random.default_rng(seed)
    genes = pd.Index([f"G{i:03d}" for i in range(n_genes)])
    rows = []
    for t in range(12):                              # 12 terms of 8-40 genes
        for g in rng.choice(genes, rng.integers(8, 40), replace=False):
            rows.append((g, f"GO:{t:07d}"))
    rows += [(g, "GO:9999999") for g in genes[:3]]   # too small -> dropped
    rows += [(g, "GO:8888888") for g in genes]       # too large -> dropped
    return genes, pd.DataFrame(rows, columns=["gene", "go_id"]).drop_duplicates()


def test_term_sets_respect_size_bounds():
    genes, go = _annotation_universe()
    ts = build_term_sets(go, genes, min_size=5, max_size=100)
    assert "GO:9999999" not in ts.terms and "GO:8888888" not in ts.terms
    assert ts.sizes.min() >= 5 and ts.sizes.max() <= 100
    assert (ts.matrix.sum(axis=0).A1 == ts.sizes).all()


def test_enrich_gene_set_matches_fisher_exact():
    genes, go = _annotation_universe()
    ts = build_term_sets(go, genes, min_size=5, max_size=100)
    term = ts.terms[0]
    members = list(ts.genes[ts.matrix[:, 0].nonzero()[0]])
    query = members[:10] + [g for g in ts.genes if g not in members][:10]            # 10 of the term + 10 others
    table = enrich_gene_set(query, ts, alpha=1.0, min_overlap=2).set_index("term")
    row = table.loc[term]
    a = row["overlap"]
    b = len(query) - a
    c = row["term_size"] - a
    d = ts.n_genes - a - b - c
    _, p_fisher = fisher_exact([[a, b], [c, d]], alternative="greater")
    assert row["p_value"] == pytest.approx(p_fisher, rel=1e-6)
    assert row["fold_enrichment"] == pytest.approx((a / len(query)) / (row["term_size"] / ts.n_genes))
    significant = enrich_gene_set(query, ts, alpha=0.05)
    assert term in set(significant["term"]) and (significant["q_value"] <= 0.05).all()
    assert enrich_gene_set(["not-a-gene"], ts).empty


def test_neighbourhood_enrichment_equals_per_gene_enrichment():
    genes, go = _annotation_universe()
    ts = build_term_sets(go, genes, min_size=5, max_size=100)
    rng = np.random.default_rng(5)
    focus = ts.genes[ts.matrix[:, 1].nonzero()[0]]
    rows = []
    for gene in ["G000", "G001", "G002"]:
        picks = list(focus[:15]) if gene == "G000" else list(rng.choice(ts.genes, 15, replace=False))
        rows += [(gene, nb) for nb in picks if nb != gene]
    nbrs = pd.DataFrame(rows, columns=["gene_id", "neighbour_id"])
    fast = neighbourhood_enrichment(nbrs, ts, alpha=1.0, min_overlap=2)
    for gene, sub in nbrs.groupby("gene_id"):
        slow = enrich_gene_set(list(sub["neighbour_id"]), ts, alpha=1.0, min_overlap=2).set_index("term")
        got = fast[fast["gene_id"] == gene].set_index("term")
        assert set(got.index) == set(slow.index)
        assert np.allclose(got.loc[slow.index, "p_value"], slow["p_value"])
        assert np.allclose(got.loc[slow.index, "q_value"], slow["q_value"])


def test_select_edges_are_unique_undirected_and_respect_both_cuts():
    tpm, study, modules = _synthetic()
    prepared = prepare_expression(tpm, study, "within_study", PARAMS, genes=tpm.index)
    nb = top_neighbours(prepared.z, 9)
    table = neighbour_table(prepared.genes, nb, correlation_null(prepared.z, 5000, 0))
    gi = np.repeat(np.arange(len(prepared.genes)), 9)
    table["within_study_median_r"], table["n_studies_tested"] = study_consistency(prepared, gi, nb.idx.ravel(), PARAMS)

    edges = select_edges(table, max_mutual_rank=9)
    assert (edges["a"] < edges["b"]).all() and not edges.duplicated(["a", "b"]).any()
    # a module of 8 genes, every pair mutually within rank 7: 28 undirected edges, listed from both sides in the table
    m0 = set(modules[0])
    assert len(edges[edges["a"].isin(m0) & edges["b"].isin(m0)]) == 28
    assert (edges["mutual_rank"] <= 9).all()
    strict = select_edges(table, max_mutual_rank=9, min_within_study_r=0.99)
    assert len(strict) < len(edges) and (strict["within_study_median_r"] >= 0.99).all()
    assert len(select_edges(table, max_mutual_rank=0)) == 0
