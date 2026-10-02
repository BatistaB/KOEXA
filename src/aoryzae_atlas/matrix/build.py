"""Build gene x sample and gene x condition TPM matrices from DuckDB.

Unit-of-analysis discipline (PROJECT_MASTER_SPEC.md section 8 / AGENTS.md
"never average biological replicates during ingestion"):

    sample-level TPM (gene_expression table, untouched)
        -> collapse TECHNICAL replicates only (mean; same biosample,
           re-sequenced) into one biological-replicate-level value
        -> aggregate BIOLOGICAL replicates within a condition (median,
           the spec's default robust condition-level abundance) into the
           condition-level matrix

Nothing here ever overwrites `gene_expression`; every function returns a
new DataFrame.
"""
from __future__ import annotations

import duckdb
import numpy as np
import pandas as pd

__all__ = [
    "fetch_gene_sample_tpm",
    "pivot_gene_by_sample",
    "fetch_sample_condition_map",
    "collapse_technical_replicates",
    "fetch_biosample_units",
    "collapse_to_biosamples",
    "condition_level_stats",
    "pivot_gene_by_condition",
]


def fetch_gene_sample_tpm(conn: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    """Long-format (sample_id, canonical_gene_id, TPM) for QUANTIFIED samples only."""
    return conn.execute(
        """
        SELECT ge.sample_id, ge.canonical_gene_id, ge.TPM
        FROM gene_expression ge
        JOIN samples s ON s.sample_id = ge.sample_id
        WHERE s.pipeline_status = 'QUANTIFIED'
        """
    ).fetchdf()


def pivot_gene_by_sample(long_df: pd.DataFrame) -> pd.DataFrame:
    """(genes x samples) wide TPM matrix, gene rows sorted, sample columns sorted."""
    wide = long_df.pivot_table(index="canonical_gene_id", columns="sample_id", values="TPM", aggfunc="first")
    return wide.sort_index().sort_index(axis=1)


def fetch_sample_condition_map(conn: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    """(sample_id, condition_id, biological_replicate, technical_replicate, bioproject) for curated, quantified samples."""
    return conn.execute(
        """
        SELECT sample_id, condition_id, biological_replicate, technical_replicate, bioproject
        FROM samples
        WHERE pipeline_status = 'QUANTIFIED' AND condition_id IS NOT NULL
        """
    ).fetchdf()


def collapse_technical_replicates(long_df: pd.DataFrame, sample_condition_map: pd.DataFrame) -> pd.DataFrame:
    """Mean TPM across technical replicates (same condition + biological_replicate) -> one row per (gene, condition_id, biological_replicate).

    Samples not present in `sample_condition_map` (no curated condition yet)
    are dropped, not guessed at.
    """
    merged = long_df.merge(sample_condition_map, on="sample_id", how="inner")
    grouped = (
        merged.groupby(["canonical_gene_id", "condition_id", "biological_replicate"], as_index=False)["TPM"]
        .mean()
    )
    return grouped


def fetch_biosample_units(conn: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    """One row per QUANTIFIED run: sample_id, unit_id, bioproject, strain, biosample.

    `unit_id` is the independent biological sample (bioproject + biosample
    accession). Runs sharing a biosample are re-sequencing of the same
    material and must not count as independent evidence. A run with no
    biosample accession falls back to being its own unit (never merged by
    guesswork).
    """
    return conn.execute(
        """
        SELECT sample_id,
               bioproject || '|' || COALESCE(NULLIF(biosample, ''), sample_id) AS unit_id,
               bioproject,
               NULLIF(strain, '') AS strain,
               biosample
        FROM samples
        WHERE pipeline_status = 'QUANTIFIED'
        """
    ).fetchdf()


def collapse_to_biosamples(long_df: pd.DataFrame, units: pd.DataFrame) -> pd.DataFrame:
    """(genes x biosample-units) TPM matrix: mean TPM across the runs of each unit.

    Mean (not sum) so a re-sequenced biosample keeps its own TPM scale; the
    sample-level `gene_expression` table is never modified.
    """
    merged = long_df.merge(units[["sample_id", "unit_id"]], on="sample_id", how="inner")
    wide = merged.pivot_table(index="canonical_gene_id", columns="unit_id", values="TPM", aggfunc="mean")
    return wide.sort_index().sort_index(axis=1)


def condition_level_stats(replicate_df: pd.DataFrame) -> pd.DataFrame:
    """Per (gene, condition): n_replicates, median/mean/SD/MAD_TPM across BIOLOGICAL replicates.

    SD and MAD are NaN (not 0) when n_replicates == 1 -- a single
    observation carries no variance estimate; reporting 0 would falsely
    claim certainty. MAD here is the standard median absolute deviation
    without the 1.4826 normal-consistency scale factor (that scaling is
    applied only in the robust_CV statistic in stats.py, where
    comparability to SD matters).
    """
    key = ["canonical_gene_id", "condition_id"]
    grouped = replicate_df.groupby(key)["TPM"]

    # Vectorized (no per-group Python calls): pandas' std(ddof=1) already
    # returns NaN for a size-1 group on its own; MAD needs an explicit mask
    # since abs(x - median(x)) is trivially 0 for a single observation,
    # which would otherwise misreport "zero variability" instead of
    # "no variability estimate possible".
    n_replicates = grouped.size().rename("n_replicates")
    median_tpm = grouped.median().rename("median_TPM")
    mean_tpm = grouped.mean().rename("mean_TPM")
    sd_tpm = grouped.std(ddof=1).rename("SD_TPM")

    group_median = grouped.transform("median")
    abs_dev = (replicate_df["TPM"] - group_median).abs()
    mad_tpm = abs_dev.groupby([replicate_df["canonical_gene_id"], replicate_df["condition_id"]]).median()
    mad_tpm = mad_tpm.rename("MAD_TPM")
    mad_tpm[n_replicates.reindex(mad_tpm.index) == 1] = np.nan

    return pd.concat([n_replicates, median_tpm, mean_tpm, sd_tpm, mad_tpm], axis=1).reset_index()


def pivot_gene_by_condition(condition_stats: pd.DataFrame, value_col: str = "median_TPM") -> pd.DataFrame:
    """(genes x conditions) wide matrix built from `condition_level_stats` output."""
    wide = condition_stats.pivot_table(index="canonical_gene_id", columns="condition_id", values=value_col, aggfunc="first")
    return wide.sort_index().sort_index(axis=1)
