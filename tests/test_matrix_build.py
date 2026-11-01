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


def test_biosample_units_split_a_biosample_that_spans_several_conditions(tmp_path):
    import duckdb

    from aoryzae_atlas.database.migrate import apply_migrations
    from aoryzae_atlas.matrix.build import fetch_biosample_units

    db_path = tmp_path / "units.duckdb"
    apply_migrations(db_path)
    rows = [
        # (sample_id, biosample, bioproject, condition_id)
        ("r1", "BS_A", "PRJ1", "PRJ1_x"),   # re-sequenced twice inside one condition: one unit
        ("r2", "BS_A", "PRJ1", "PRJ1_x"),
        ("r3", "BS_B", "PRJ1", "PRJ1_x"),   # one BioSample registered for two cultures: two units
        ("r4", "BS_B", "PRJ1", "PRJ1_y"),
        ("r5", "BS_C", "PRJ1", None),       # one curated condition plus an uncurated run: still one unit
        ("r6", "BS_C", "PRJ1", "PRJ1_x"),
        ("r9", "BS_D", "PRJ1", "PRJ1_x"),   # two conditions plus an uncurated run: the uncurated one keeps the plain unit
        ("r10", "BS_D", "PRJ1", "PRJ1_y"),
        ("r11", "BS_D", "PRJ1", None),
        ("r7", "", "PRJ1", "PRJ1_x"),       # no biosample accession: its own unit, whatever the condition
        ("r8", "", "PRJ1", "PRJ1_y"),
    ]
    conn = duckdb.connect(str(db_path))
    for sample_id, biosample, bioproject, condition_id in rows:
        conn.execute(
            "INSERT INTO samples (sample_id, run_accession, biosample, bioproject, condition_id, pipeline_status) "
            "VALUES (?, ?, ?, ?, ?, 'QUANTIFIED')",
            [sample_id, sample_id, biosample, bioproject, condition_id],
        )
    units = fetch_biosample_units(conn).set_index("sample_id")["unit_id"].to_dict()
    conn.close()
    assert units["r1"] == units["r2"] == "PRJ1|BS_A"
    assert units["r3"] == "PRJ1|BS_B|PRJ1_x" and units["r4"] == "PRJ1|BS_B|PRJ1_y"
    assert units["r5"] == units["r6"] == "PRJ1|BS_C"
    assert units["r9"] == "PRJ1|BS_D|PRJ1_x" and units["r10"] == "PRJ1|BS_D|PRJ1_y" and units["r11"] == "PRJ1|BS_D"
    assert units["r7"] == "PRJ1|r7" and units["r8"] == "PRJ1|r8"


def test_biosample_units_take_the_strain_from_the_curated_condition_first(tmp_path):
    import duckdb

    from aoryzae_atlas.database.migrate import apply_migrations
    from aoryzae_atlas.matrix.build import fetch_biosample_units

    db_path = tmp_path / "strain.duckdb"
    apply_migrations(db_path)
    conn = duckdb.connect(str(db_path))
    conn.execute("INSERT INTO conditions (condition_id, strain) VALUES ('PRJ1_x', 'RIB40'), ('PRJ1_blank', '')")
    rows = [
        # (sample_id, raw strain, condition_id)
        ("s1", "", "PRJ1_x"),              # blank raw strain: the curated one fills it
        ("s2", "WT-2", "PRJ1_x"),          # free-text raw label: the curated one wins
        ("s3", "RIB915", "PRJ1_blank"),    # condition without a strain: the raw one is kept
        ("s4", "RIB333", None),            # no curated condition: the raw one is kept
        ("s5", "", None),                  # nothing known: stays unknown
    ]
    for sample_id, strain, condition_id in rows:
        conn.execute(
            "INSERT INTO samples (sample_id, run_accession, biosample, bioproject, strain, condition_id, pipeline_status) "
            "VALUES (?, ?, ?, 'PRJ1', ?, ?, 'QUANTIFIED')",
            [sample_id, sample_id, f"BS_{sample_id}", strain, condition_id],
        )
    strains = fetch_biosample_units(conn).set_index("sample_id")["strain"].to_dict()
    conn.close()
    assert strains["s1"] == "RIB40" and strains["s2"] == "RIB40"
    assert strains["s3"] == "RIB915" and strains["s4"] == "RIB333"
    assert strains["s5"] is None or strains["s5"] != strains["s5"]  # NULL / NaN


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
