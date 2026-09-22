"""Tests for aoryzae_atlas.matrix.stats (Milestone 9)."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from aoryzae_atlas.matrix.stats import (
    abundance_stats,
    compute_gene_feature_table,
    gini,
    log2_tpm,
    prevalence,
    tau,
    variability_stats,
)


def test_tau_broad_flat_expression_is_zero():
    assert tau(np.array([10.0, 10.0, 10.0, 10.0])) == pytest.approx(0.0)


def test_tau_broad_expression_ignores_absolute_level():
    # section 6 of the spec: flat-100 and flat-1 both read as broad (Tau ~ 0)
    # despite very different abundance.
    assert tau(np.array([100.0] * 5)) == pytest.approx(0.0)
    assert tau(np.array([1.0] * 5)) == pytest.approx(0.0)


def test_tau_single_condition_specific_is_one():
    assert tau(np.array([0.0, 0.0, 0.0, 100.0])) == pytest.approx(1.0)


def test_tau_known_intermediate_value():
    # x_hat = [1, 0.5, 0, 0] -> tau = (0 + 0.5 + 1 + 1) / 3 = 0.8333...
    assert tau(np.array([100.0, 50.0, 0.0, 0.0])) == pytest.approx(2.5 / 3)


def test_tau_undefined_for_all_zero():
    assert np.isnan(tau(np.array([0.0, 0.0, 0.0])))


def test_tau_undefined_for_fewer_than_two_conditions():
    assert np.isnan(tau(np.array([5.0])))


def test_log2_tpm_matches_spec_formula():
    # spec section 5: log1p_TPM = log2(TPM + 1), explicitly base 2.
    assert log2_tpm(np.array([3.0]))[0] == pytest.approx(2.0)  # log2(4) = 2


def test_gini_uniform_is_zero_and_concentrated_is_high():
    assert gini(np.array([10.0, 10.0, 10.0])) == pytest.approx(0.0)
    concentrated = gini(np.array([0.0, 0.0, 0.0, 100.0]))
    assert concentrated > 0.5


def test_prevalence_counts_fraction_at_or_above_threshold():
    assert prevalence(np.array([0.0, 0.5, 1.0, 5.0]), threshold=1.0) == pytest.approx(0.5)


def test_abundance_stats_basic():
    stats = abundance_stats(np.array([1.0, 2.0, 3.0, 4.0]))
    assert stats["median_TPM"] == pytest.approx(2.5)
    assert stats["max_TPM"] == pytest.approx(4.0)


def test_variability_stats_robust_cv_survives_zero_mean_edge_case():
    # A gene detected in only one of several conditions: mean is small but
    # nonzero, median is 0 -> robust_CV must be NaN, not a division blow-up.
    stats = variability_stats(np.array([0.0, 0.0, 0.0, 5.0]))
    assert np.isnan(stats["robust_CV"])
    assert not np.isnan(stats["CV"])


def test_variability_stats_single_value_is_nan_not_zero():
    stats = variability_stats(np.array([5.0]))
    assert np.isnan(stats["CV"])
    assert np.isnan(stats["MAD"])


def test_compute_gene_feature_table_prevalence_column_names_match_spec():
    matrix = pd.DataFrame({"condA": [0.0], "condB": [2.0]}, index=["gene1"])
    table = compute_gene_feature_table(matrix, prevalence_thresholds=(0.1, 1.0, 5.0))
    assert {"prevalence_TPM_0.1", "prevalence_TPM_1", "prevalence_TPM_5"} <= set(table.columns)


def test_compute_gene_feature_table_shape_and_columns():
    matrix = pd.DataFrame(
        {"condA": [10.0, 0.0], "condB": [10.0, 0.0], "condC": [10.0, 100.0]},
        index=["geneFlat", "geneSpecific"],
    )
    table = compute_gene_feature_table(matrix)
    assert list(table.index) == ["geneFlat", "geneSpecific"]
    assert table.loc["geneFlat", "Tau_raw"] == pytest.approx(0.0)
    assert table.loc["geneSpecific", "Tau_raw"] == pytest.approx(1.0)
    assert table.loc["geneSpecific", "max_expression_condition"] == "condC"
    assert table.loc["geneFlat", "n_detected_conditions"] == 3
    assert table.loc["geneSpecific", "n_detected_conditions"] == 1
