"""Vectorized per-gene distribution metrics over a (genes x samples) TPM matrix.

The unit of analysis is the independent biological sample (biosample);
technical replicates are collapsed upstream (`matrix.build.collapse_to_biosamples`).

Dispersion is measured on log2(TPM + 1) with robust statistics (MAD, IQR);
CV is computed only as a secondary column because it explodes for
lowly-expressed genes. Ratios use a +1 TPM pseudocount (same as the log
transform) because the raw ratio is infinite/undefined for every gene whose
median is 0.
"""
from __future__ import annotations

import math

import numpy as np
import pandas as pd

__all__ = ["PREVALENCE_THRESHOLDS", "log2_tpm", "tau_rows", "peak_share_rows", "compute_gene_metrics"]

PREVALENCE_THRESHOLDS: tuple[float, ...] = (0.1, 1.0, 5.0)


def log2_tpm(tpm: np.ndarray) -> np.ndarray:
    """log2(TPM + 1) -- base 2, same transform used for the Tau/robust statistics."""
    return np.log2(np.asarray(tpm, dtype=float) + 1.0)


def tau_rows(x: np.ndarray) -> np.ndarray:
    """Row-wise Tau (Kryuchkova-Mostacci & Robinson-Rechavi 2017): sum(1 - x/max) / (n-1).

    NaN when a row has fewer than 2 valid samples or its maximum is <= 0
    (a never-expressed gene has no defined specificity, not 'perfectly broad').
    """
    x = np.asarray(x, dtype=float)
    valid = ~np.isnan(x)
    n_valid = valid.sum(axis=1)
    peak = np.nanmax(np.where(valid, x, -np.inf), axis=1)
    with np.errstate(divide="ignore", invalid="ignore"):
        x_hat = np.where(valid, x / peak[:, None], 0.0)
        total = np.where(valid, 1.0 - x_hat, 0.0).sum(axis=1)
        tau = total / (n_valid - 1)
    tau[(n_valid < 2) | ~(peak > 0)] = np.nan
    return tau


def peak_share_rows(x: np.ndarray, top_fraction: float = 0.10) -> np.ndarray:
    """Share of a gene's total TPM held by its top `top_fraction` of samples (at least 1).

    ~1 means the expression is concentrated in a handful of samples
    (context-specific burst); ~top_fraction means it is spread evenly.
    NaN for genes with zero total expression.
    """
    x = np.asarray(x, dtype=float)
    n = x.shape[1]
    k = max(1, math.ceil(top_fraction * n))
    sorted_desc = -np.sort(-np.where(np.isnan(x), 0.0, x), axis=1)
    total = sorted_desc.sum(axis=1)
    with np.errstate(divide="ignore", invalid="ignore"):
        share = sorted_desc[:, :k].sum(axis=1) / total
    share[~(total > 0)] = np.nan
    return share


def compute_gene_metrics(
    tpm: pd.DataFrame,
    prevalence_thresholds: tuple[float, ...] = PREVALENCE_THRESHOLDS,
    top_fraction: float = 0.10,
) -> pd.DataFrame:
    """One row per gene with every global-distribution metric the classification uses.

    `tpm` is genes x independent samples, raw TPM (never log-transformed).
    """
    x = tpm.to_numpy(dtype=float)
    n_samples = x.shape[1]
    logx = log2_tpm(x)

    # Salmon reports every gene in every sample, so the matrix is normally complete;
    # the NaN-aware numpy functions are several times slower and only used when needed.
    complete = not np.isnan(x).any()
    median = np.median if complete else np.nanmedian
    percentile = np.percentile if complete else np.nanpercentile

    out = pd.DataFrame(index=tpm.index)
    out["n_samples"] = n_samples

    out["median_TPM"] = median(x, axis=1)
    out["mean_TPM"] = np.mean(x, axis=1) if complete else np.nanmean(x, axis=1)
    out["median_logTPM"] = median(logx, axis=1)
    p10, p25, p75, p90 = percentile(x, [10, 25, 75, 90], axis=1)
    out["P10_TPM"], out["P25_TPM"], out["P75_TPM"], out["P90_TPM"] = p10, p25, p75, p90

    q25, q75 = percentile(logx, [25, 75], axis=1)
    out["IQR_logTPM"] = q75 - q25
    out["MAD_logTPM"] = median(np.abs(logx - out["median_logTPM"].to_numpy()[:, None]), axis=1)

    for t in prevalence_thresholds:
        label = str(int(t)) if float(t).is_integer() else str(t)
        out[f"prevalence_TPM_{label}"] = np.nanmean(x >= t, axis=1)
    out["n_detected_TPM_1"] = np.nansum(x >= 1.0, axis=1).astype(int)

    out["max_TPM"] = np.nanmax(x, axis=1)
    out["max_to_median_ratio"] = (out["max_TPM"] + 1.0) / (out["median_TPM"] + 1.0)
    out["P90_to_median_ratio"] = (out["P90_TPM"] + 1.0) / (out["median_TPM"] + 1.0)

    out["Tau"] = tau_rows(logx)
    out["Tau_raw"] = tau_rows(x)
    out["peak_share_top10pct"] = peak_share_rows(x, top_fraction)

    sd = np.std(x, axis=1, ddof=1) if complete else np.nanstd(x, axis=1, ddof=1)
    with np.errstate(divide="ignore", invalid="ignore"):
        cv = sd / out["mean_TPM"].to_numpy()
    cv[~(out["mean_TPM"].to_numpy() > 0)] = np.nan
    out["CV_secondary"] = cv
    return out
