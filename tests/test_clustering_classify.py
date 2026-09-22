"""Tests for aoryzae_atlas.clustering.classify (Milestone 9-11 pipeline)."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from aoryzae_atlas.clustering.classify import (
    build_cluster_profile,
    classify_genes,
    select_k_by_silhouette,
    suggest_label,
)

VALID_LABELS = {
    "condition_specific",
    "rarely_expressed",
    "variable_broad",
    "constitutive_high",
    "constitutive_medium",
}


def _two_archetype_matrix() -> pd.DataFrame:
    # 10 flat, highly-expressed "constitutive" genes vs. 10 single-condition
    # "specific" genes across 6 conditions -- an unambiguous 2-cluster case.
    conditions = [f"cond{i}" for i in range(6)]
    rows = {}
    for i in range(10):
        rows[f"const{i}"] = [500.0 + i] * 6
    for i in range(10):
        values = [1.0] * 6
        values[i % 6] = 2000.0
        rows[f"spec{i}"] = values
    return pd.DataFrame(rows, index=conditions).T[conditions]


def test_select_k_by_silhouette_finds_two_clusters():
    matrix = _two_archetype_matrix()
    from aoryzae_atlas.clustering.features import assemble_base_features, standardize
    from aoryzae_atlas.matrix.stats import compute_gene_feature_table

    feature_table = compute_gene_feature_table(matrix)
    base = assemble_base_features(feature_table).dropna()
    X = standardize(base)
    k, scores = select_k_by_silhouette(X, k_range=range(2, 5), seed=0)
    assert k == 2
    assert set(scores.index) == {2, 3, 4}


def test_suggest_label_high_tau_is_condition_specific():
    profile = pd.DataFrame(
        {
            "mean_log1p_median_TPM": [5.0, 1.0],
            "mean_prevalence_TPM_1": [1.0, 0.2],
            "mean_robust_CV": [0.1, 0.2],
            "mean_Tau_log1p": [0.1, 0.9],
        },
        index=[0, 1],
    )
    assert suggest_label(profile.loc[1], profile) == "condition_specific"


def test_build_cluster_profile_sorted_by_abundance_desc():
    base_features = pd.DataFrame(
        {
            "log1p_median_TPM": [1.0, 1.1, 9.0, 9.2],
            "prevalence_TPM_1": [0.2, 0.2, 1.0, 1.0],
            "robust_CV": [0.3, 0.3, 0.1, 0.1],
            "Tau_log1p": [0.1, 0.1, 0.1, 0.1],
        },
        index=["g1", "g2", "g3", "g4"],
    )
    labels = pd.Series([0, 0, 1, 1], index=base_features.index)
    profile = build_cluster_profile(base_features, labels)
    assert profile.iloc[0].name == 1  # highest mean_log1p_median_TPM first
    assert profile.loc[1, "n_genes"] == 2


def test_classify_genes_end_to_end_two_archetypes():
    matrix = _two_archetype_matrix()
    result = classify_genes(matrix, k_range=range(2, 5), seed=0)

    assert result.k_base == 2
    assert set(result.final_table.index) == set(matrix.index)
    labelled = result.final_table["biological_label"].dropna()
    assert len(labelled) == 20
    assert set(labelled.unique()) <= VALID_LABELS

    # The 10 flat/high genes and 10 specific genes must land in different clusters.
    const_labels = result.final_table.loc[[f"const{i}" for i in range(10)], "biological_label"]
    spec_labels = result.final_table.loc[[f"spec{i}" for i in range(10)], "biological_label"]
    assert set(const_labels.unique()) != set(spec_labels.unique())
    assert (spec_labels == "condition_specific").all()

    assert (result.final_table["classification_confidence"] == "medium").all()


def test_classify_genes_low_confidence_for_sparse_detection():
    conditions = [f"c{i}" for i in range(6)]
    matrix = pd.DataFrame(
        {
            # Sparse: detected in only 1 condition -- classification_confidence
            # is about the whole feature_table (all genes), independent of
            # which genes have valid-enough BASE features to be clustered.
            "g1": [10.0, 0.0, 0.0, 0.0, 0.0, 0.0],
            "g2": [10.0, 12.0, 11.0, 9.0, 10.0, 11.0],
            "g3": [40.0, 38.0, 42.0, 39.0, 41.0, 37.0],
            "g4": [5.0, 6.0, 5.0, 4.0, 6.0, 5.0],
        },
        index=conditions,
    ).T[conditions]
    result = classify_genes(matrix, k_range=range(2, 3), seed=0)
    assert result.final_table.loc["g1", "classification_confidence"] == "low"
    assert result.final_table.loc["g2", "classification_confidence"] == "medium"
