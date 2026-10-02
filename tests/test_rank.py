"""Tests for aoryzae_atlas.rank (pan-transcriptomic expression rank)."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from aoryzae_atlas.matrix.build import collapse_to_biosamples
from aoryzae_atlas.matrix.stats import tau as tau_scalar
from aoryzae_atlas.rank.classes import (
    CLASS_ORDER,
    ClassParams,
    assign_classes,
    class_agreement,
    class_stability,
    derive_thresholds,
)
from aoryzae_atlas.rank.diagnostics import benjamini_hochberg, build_quality_flags, group_dominance
from aoryzae_atlas.rank.metrics import compute_gene_metrics, log2_tpm, peak_share_rows, tau_rows
from aoryzae_atlas.rank.scores import compute_scores, pct_rank
from aoryzae_atlas.rank.validation import build_gene_sets, class_enrichment, load_go_annotations

# The two behaviors the spec says must be distinguishable (section 7).
EXAMPLE_A_BROAD_VARIABLE = [10, 30, 60, 15, 80, 40, 100, 25]
EXAMPLE_B_CONTEXT_SPECIFIC = [0, 0, 0.2, 0, 1, 0, 350, 0]


def _two_gene_matrix() -> pd.DataFrame:
    return pd.DataFrame(
        [EXAMPLE_A_BROAD_VARIABLE, EXAMPLE_B_CONTEXT_SPECIFIC],
        index=["A_broad_variable", "B_context_specific"],
        columns=[f"s{i}" for i in range(8)],
        dtype=float,
    )


def test_tau_rows_matches_scalar_tau():
    rng = np.random.default_rng(0)
    x = rng.gamma(2.0, 5.0, size=(50, 12))
    x[3] = 0.0
    vectorized = tau_rows(x)
    for i in range(len(x)):
        expected = tau_scalar(x[i])
        if np.isnan(expected):
            assert np.isnan(vectorized[i])
        else:
            assert vectorized[i] == pytest.approx(expected)


def test_tau_rows_undefined_for_silent_gene():
    assert np.isnan(tau_rows(np.zeros((1, 5)))[0])


def test_peak_share_distinguishes_burst_from_spread():
    shares = peak_share_rows(np.array([EXAMPLE_A_BROAD_VARIABLE, EXAMPLE_B_CONTEXT_SPECIFIC], dtype=float), 0.10)
    assert shares[0] < 0.35  # expression spread across samples
    assert shares[1] > 0.95  # almost all expression in one sample


def test_metrics_separate_variable_from_context_specific():
    m = compute_gene_metrics(_two_gene_matrix())
    a, b = m.loc["A_broad_variable"], m.loc["B_context_specific"]
    assert a["prevalence_TPM_1"] == 1.0 and b["prevalence_TPM_1"] < 0.5
    assert b["Tau"] > a["Tau"]
    assert b["peak_share_top10pct"] > a["peak_share_top10pct"]
    assert b["max_to_median_ratio"] > a["max_to_median_ratio"]
    assert a["median_TPM"] == pytest.approx(35.0)


def test_metrics_use_log2_and_unscaled_mad():
    m = compute_gene_metrics(_two_gene_matrix())
    logx = log2_tpm(np.array(EXAMPLE_A_BROAD_VARIABLE, dtype=float))
    assert m.loc["A_broad_variable", "median_logTPM"] == pytest.approx(np.median(logx))
    assert m.loc["A_broad_variable", "MAD_logTPM"] == pytest.approx(np.median(np.abs(logx - np.median(logx))))
    assert log2_tpm(np.array([3.0]))[0] == pytest.approx(2.0)


def test_metrics_columns_cover_spec():
    m = compute_gene_metrics(_two_gene_matrix())
    for col in [
        "median_TPM", "mean_TPM", "median_logTPM", "P10_TPM", "P25_TPM", "P75_TPM", "P90_TPM",
        "IQR_logTPM", "MAD_logTPM", "prevalence_TPM_0.1", "prevalence_TPM_1", "prevalence_TPM_5",
        "max_TPM", "max_to_median_ratio", "P90_to_median_ratio", "Tau", "n_samples",
    ]:
        assert col in m.columns


def test_ratios_are_finite_for_zero_median_genes():
    m = compute_gene_metrics(_two_gene_matrix())
    assert np.isfinite(m.loc["B_context_specific", "max_to_median_ratio"])


def test_pct_rank_in_unit_interval():
    r = pct_rank(pd.Series([5.0, 1.0, 3.0, 3.0]))
    assert r.max() == 1.0 and r.min() > 0


def _synthetic_atlas(n_samples: int = 60, seed: int = 1) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    rows, names = [], []
    for i in range(80):  # stable high
        rows.append(np.exp(rng.normal(6.0, 0.15, n_samples))); names.append(f"hi{i}")
    for i in range(160):  # stable mid (variable genes are ~20% of this tier, the design's tail share)
        rows.append(np.exp(rng.normal(3.0, 0.2, n_samples))); names.append(f"mid{i}")
    for i in range(40):  # broad but variable (log2 MAD ~0.9, like the real variable class), not bursty
        rows.append(np.exp(rng.normal(3.5, 0.9, n_samples))); names.append(f"var{i}")
    for i in range(50):  # bursts in a few samples
        burst = np.zeros(n_samples); burst[rng.choice(n_samples, 3, replace=False)] = rng.uniform(80, 400, 3)
        rows.append(burst); names.append(f"ctx{i}")
    for i in range(40):  # essentially silent
        rows.append(rng.uniform(0, 0.02, n_samples)); names.append(f"sil{i}")
    return pd.DataFrame(rows, index=names, columns=[f"s{j}" for j in range(n_samples)])


def test_classes_recover_planted_groups():
    m = compute_gene_metrics(_synthetic_atlas())
    classes = assign_classes(m).astype(str)
    prefix = classes.index.str.extract(r"^([a-z]+)", expand=False)
    assert (classes[prefix == "ctx"] == "Context-Specific").mean() > 0.9
    assert (classes[prefix == "sil"] == "Rare/Silent").mean() > 0.9
    # Classes are relative (high-dispersion/Tau tails are cut within each level tier), so even a perfectly
    # homogeneous stable group sheds its own tail: assert it never lands in an opposite class, and mostly constitutive.
    hi = classes[prefix == "hi"]
    assert hi.str.startswith("Constitutive").mean() > 0.6
    assert not hi.isin(["Context-Specific", "Rare/Silent"]).any()
    # Thresholds are population quantiles, so how a variable gene is labeled depends on the population's mix;
    # what must always hold is that a highly dispersed gene is never called constitutive.
    assert (~classes[prefix == "var"].str.startswith("Constitutive")).mean() > 0.9
    assert set(classes.unique()) <= set(CLASS_ORDER)


def test_every_gene_gets_exactly_one_class():
    m = compute_gene_metrics(_synthetic_atlas())
    classes = assign_classes(m)
    assert classes.notna().all() and len(classes) == len(m)


def test_thresholds_are_derived_not_fixed():
    low = derive_thresholds(compute_gene_metrics(_synthetic_atlas()))
    shifted = _synthetic_atlas() * 10.0
    high = derive_thresholds(compute_gene_metrics(shifted))
    assert high.level_high > low.level_high  # thresholds move with the data


def test_class_stability_in_unit_interval_and_agreement():
    m = compute_gene_metrics(_synthetic_atlas())
    stability, summary = class_stability(m)
    assert stability.between(0, 1).all() and len(summary) == 10
    base = assign_classes(m)
    assert class_agreement(base, base) == 1.0


def test_scores_keep_components_and_orderings():
    m = compute_gene_metrics(_synthetic_atlas())
    s = compute_scores(m)
    for col in [
        "expression_level_score", "expression_stability_score", "expression_specificity_score",
        "expression_prevalence_score", "global_expression_rank", "rank_most_expressed", "rank_most_stable",
        "rank_most_variable", "rank_most_specific", "rank_rarest",
    ]:
        assert col in s.columns
    assert s.global_expression_rank.min() == 1
    assert s.loc["hi0":"hi5", "expression_level_score"].min() > s.loc["sil0":"sil5", "expression_level_score"].max()


def test_silent_genes_cannot_rank_as_stable_or_specific():
    m = compute_gene_metrics(_synthetic_atlas())
    s = compute_scores(m)
    assert s.loc[s.index.str.startswith("sil"), "expression_stability_score"].median() < s.loc[
        s.index.str.startswith("hi"), "expression_stability_score"
    ].median()
    assert s.loc[s.index.str.startswith("sil"), "rank_most_specific"].min() > 20


def test_group_dominance_flags_single_study_gene():
    samples = [f"s{i}" for i in range(40)]
    groups = pd.Series(["A"] * 20 + ["B"] * 20, index=samples)
    rng = np.random.default_rng(3)
    tpm = pd.DataFrame(rng.uniform(1, 5, (2, 40)), index=["balanced", "studyA_only"], columns=samples)
    tpm.loc["studyA_only", samples[:20]] = rng.uniform(100, 200, 20)
    d = group_dominance(tpm, groups)
    assert d.loc["studyA_only", "dominant_group"] == "A"
    assert d.loc["studyA_only", "dominance"] == 1.0
    assert d.loc["studyA_only", "dominance_q"] < d.loc["balanced", "dominance_q"]


def test_benjamini_hochberg_monotone_and_nan_safe():
    q = benjamini_hochberg(np.array([0.001, 0.04, np.nan, 0.5]))
    assert np.isnan(q[2]) and q[0] <= q[1] <= q[3]


def test_build_quality_flags_joins_names():
    flags = build_quality_flags(
        {"possible_study_effect": pd.Series([True, False]), "low_sample_support": pd.Series([True, False])}
    )
    assert flags.iloc[0] == "possible_study_effect;low_sample_support" and flags.iloc[1] == ""


def test_collapse_to_biosamples_averages_runs_of_same_unit():
    long_df = pd.DataFrame(
        {"sample_id": ["r1", "r2", "r3"], "canonical_gene_id": ["G"] * 3, "TPM": [10.0, 30.0, 50.0]}
    )
    units = pd.DataFrame({"sample_id": ["r1", "r2", "r3"], "unit_id": ["P|B1", "P|B1", "P|B2"]})
    wide = collapse_to_biosamples(long_df, units)
    assert wide.loc["G", "P|B1"] == 20.0 and wide.loc["G", "P|B2"] == 50.0


def test_go_loader_and_gene_sets_and_enrichment(tmp_path):
    gaf = tmp_path / "x.gaf"
    gaf.write_text(
        "!gaf-version: 2.1\n"
        "FungiDB\tG1\tG1\t\tGO:0006412\tREF\tIEA\n"
        "FungiDB\tG2\tG2\tNOT\tGO:0006412\tREF\tIEA\n"
        "FungiDB\tG3\tG3\t\tGO:0044550\tREF\tIEA\n",
        encoding="utf-8",
    )
    go = load_go_annotations(gaf)
    assert set(go["gene"]) == {"G1", "G3"}
    universe = pd.Index(["G1", "G2", "G3", "G4"])
    desc = pd.Series({"G4": "60S ribosomal protein L3"})
    sets = build_gene_sets(go, desc, universe)
    assert sets.loc["G1", "translation_ribosome"] and sets.loc["G4", "translation_ribosome"]
    assert not sets.loc["G2", "translation_ribosome"] and sets.loc["G3", "secondary_metabolism"]

    classes = pd.Series(["Constitutive High", "Rare/Silent", "Context-Specific", "Constitutive High"], index=universe)
    table = class_enrichment(classes, sets, pd.Series([0.9, 0.1, 0.2, 0.8], index=universe))
    assert {"odds_ratio", "q_value", "fraction_of_category"} <= set(table.columns)


def test_broad_variable_class_is_more_dispersed_than_constitutive_classes():
    m = compute_gene_metrics(_synthetic_atlas())
    classes = assign_classes(m).astype(str)
    variable = m.loc[classes == "Broad Variable", "MAD_logTPM"]
    constitutive = m.loc[classes.str.startswith("Constitutive"), "MAD_logTPM"]
    assert len(variable) > 0 and variable.median() > constitutive.median()
