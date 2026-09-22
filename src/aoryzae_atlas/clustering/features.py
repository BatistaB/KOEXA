"""Feature-matrix assembly for clustering (spec section 11).

Deliberately picks ONE representative statistic per concept
(log1p(median_TPM) for abundance, prevalence_TPM_1 for prevalence,
robust_CV for variability, Tau_log1p for specificity) rather than every
column in the feature table, so redundant near-duplicate columns (mean vs
median vs Q50, Tau_raw vs Tau_log1p, CV vs robust_CV) don't let one
underlying signal dominate the distance metric just by being counted
twice -- the spec's own "do not allow redundant variables to dominate"
instruction (section 11).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

__all__ = ["BASE_FEATURE_COLUMNS", "assemble_base_features", "standardize"]

BASE_FEATURE_COLUMNS = ("log1p_median_TPM", "prevalence_TPM_1", "robust_CV", "Tau_log1p")


def assemble_base_features(gene_feature_table: pd.DataFrame) -> pd.DataFrame:
    """One column per BASE_FEATURE_COLUMNS concept, indexed by gene.

    Rows with any NaN in the selected columns are dropped (documented by
    the caller, not silently imputed -- e.g. Tau is NaN for genes
    detected in 0 or 1 condition, robust_CV is NaN when median_TPM is 0).
    """
    out = pd.DataFrame(index=gene_feature_table.index)
    out["log1p_median_TPM"] = np.log2(gene_feature_table["median_TPM"] + 1.0)
    out["prevalence_TPM_1"] = gene_feature_table["prevalence_TPM_1"]
    out["robust_CV"] = gene_feature_table["robust_CV"]
    out["Tau_log1p"] = gene_feature_table["Tau_log1p"]
    return out


def standardize(feature_df: pd.DataFrame) -> pd.DataFrame:
    """Z-score each column (mean 0, SD 1); constant columns become all-0 rather than NaN/inf."""
    mean = feature_df.mean()
    sd = feature_df.std(ddof=0).replace(0.0, np.nan)
    scaled = (feature_df - mean) / sd
    return scaled.fillna(0.0)
