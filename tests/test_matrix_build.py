"""Tests for aoryzae_atlas.matrix.build (Milestone 9 matrix assembly)."""
from __future__ import annotations

import numpy as np
import pandas as pd

from aoryzae_atlas.matrix.build import (
    collapse_technical_replicates,
    condition_level_stats,
    pivot_gene_by_condition,
    pivot_gene_by_sample,
)


def test_pivot_gene_by_sample():
    long_df = pd.DataFrame(
        {
            "sample_id": ["S1", "S1", "S2", "S2"],
            "canonical_gene_id": ["G1", "G2", "G1", "G2"],
            "TPM": [1.0, 2.0, 3.0, 4.0],
        }
    )
    wide = pivot_gene_by_sample(long_df)
    assert wide.loc["G1", "S1"] == 1.0
    assert wide.loc["G2", "S2"] == 4.0


def test_collapse_technical_replicates_averages_same_biosample_runs():
    # Mirrors the real day5 lactate condition: 3 runs of ONE biosample.
    long_df = pd.DataFrame(
        {
            "sample_id": ["run1", "run2", "run3"],
            "canonical_gene_id": ["G1", "G1", "G1"],
            "TPM": [10.0, 20.0, 30.0],
        }
    )
    sample_map = pd.DataFrame(
        {
            "sample_id": ["run1", "run2", "run3"],
            "condition_id": ["condA", "condA", "condA"],
            "biological_replicate": ["1", "1", "1"],
            "technical_replicate": ["1", "2", "3"],
            "bioproject": ["PRJ1", "PRJ1", "PRJ1"],
        }
    )
    collapsed = collapse_technical_replicates(long_df, sample_map)
    assert len(collapsed) == 1  # 3 technical runs -> 1 biological-replicate row
    assert collapsed.iloc[0]["TPM"] == 20.0  # mean(10, 20, 30)
    assert collapsed.iloc[0]["biological_replicate"] == "1"


def test_condition_level_stats_nan_variance_for_singleton_replicate():
    replicate_df = pd.DataFrame(
        {
            "canonical_gene_id": ["G1"],
            "condition_id": ["condA"],
            "biological_replicate": ["1"],
            "TPM": [10.0],
        }
    )
    stats = condition_level_stats(replicate_df)
    row = stats.iloc[0]
    assert row["n_replicates"] == 1
    assert row["median_TPM"] == 10.0
    assert np.isnan(row["SD_TPM"])
    assert np.isnan(row["MAD_TPM"])


def test_condition_level_stats_median_across_true_biological_replicates():
    replicate_df = pd.DataFrame(
        {
            "canonical_gene_id": ["G1", "G1", "G1"],
            "condition_id": ["condA", "condA", "condA"],
            "biological_replicate": ["1", "2", "3"],
            "TPM": [10.0, 20.0, 30.0],
        }
    )
    stats = condition_level_stats(replicate_df)
    row = stats.iloc[0]
    assert row["n_replicates"] == 3
    assert row["median_TPM"] == 20.0
    assert not np.isnan(row["SD_TPM"])


def test_pivot_gene_by_condition():
    condition_stats = pd.DataFrame(
        {
            "canonical_gene_id": ["G1", "G1", "G2", "G2"],
            "condition_id": ["condA", "condB", "condA", "condB"],
            "median_TPM": [1.0, 2.0, 3.0, 4.0],
        }
    )
    wide = pivot_gene_by_condition(condition_stats)
    assert wide.loc["G1", "condA"] == 1.0
    assert wide.loc["G2", "condB"] == 4.0
