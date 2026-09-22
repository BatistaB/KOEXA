"""Tests for aoryzae_atlas.clustering (Milestone 11)."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from aoryzae_atlas.clustering.features import assemble_base_features, standardize
from aoryzae_atlas.clustering.stability import cluster_label_agreement


def test_assemble_base_features_selects_one_column_per_concept():
    table = pd.DataFrame(
        {
            "median_TPM": [10.0, 0.0],
            "prevalence_TPM_1": [1.0, 0.0],
            "robust_CV": [0.1, np.nan],
            "Tau_log1p": [0.0, 1.0],
        },
        index=["geneA", "geneB"],
    )
    features = assemble_base_features(table)
    assert list(features.columns) == ["log1p_median_TPM", "prevalence_TPM_1", "robust_CV", "Tau_log1p"]
    assert features.loc["geneA", "log1p_median_TPM"] > 0


def test_standardize_constant_column_becomes_zero_not_nan():
    df = pd.DataFrame({"a": [5.0, 5.0, 5.0], "b": [1.0, 2.0, 3.0]})
    scaled = standardize(df)
    assert (scaled["a"] == 0.0).all()
    assert scaled["b"].mean() == pytest.approx(0.0)


def test_cluster_label_agreement_identical_labels_is_one():
    labels = pd.Series([0, 0, 1, 1], index=["g1", "g2", "g3", "g4"])
    assert cluster_label_agreement(labels, labels) == pytest.approx(1.0)


def test_cluster_label_agreement_restricts_to_common_genes():
    labels_a = pd.Series([0, 0, 1, 1], index=["g1", "g2", "g3", "g4"])
    labels_b = pd.Series([0, 0, 1, 1], index=["g1", "g2", "g5", "g6"])
    # Only g1, g2 in common -> perfect agreement on that subset.
    assert cluster_label_agreement(labels_a, labels_b) == pytest.approx(1.0)


def test_cluster_label_agreement_too_few_common_genes_is_nan():
    labels_a = pd.Series([0], index=["g1"])
    labels_b = pd.Series([0], index=["g1"])
    assert np.isnan(cluster_label_agreement(labels_a, labels_b))
