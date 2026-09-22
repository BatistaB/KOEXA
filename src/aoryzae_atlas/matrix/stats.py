"""Per-gene expression-behavior statistics computed across CONDITIONS
(never raw samples -- see PROJECT_MASTER_SPEC.md section 8 and
`matrix/build.py`).

Methodological reference for Tau: Kryuchkova-Mostacci & Robinson-Rechavi,
"A benchmark of gene expression tissue-specificity metrics", Briefings in
Bioinformatics 18(2):205-214, 2017 (doi:10.1093/bib/bbw008). Tau was that
benchmark's best-performing general-purpose specificity metric; we
substitute "biological condition" for their "tissue" axis, an adaptation
this project is testing, not one the paper itself validated for
A. oryzae.

Tau is a SPECIFICITY metric, not an abundance metric (section 6 of the
gene-classification spec this module implements): two genes expressed
flatly at very different absolute levels can have the same Tau. Always
read Tau alongside abundance_stats, never in place of it.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

__all__ = [
    "log2_tpm",
    "tau",
    "gini",
    "prevalence",
    "abundance_stats",
    "variability_stats",
    "compute_gene_feature_table",
]

_ROBUST_MAD_TO_SD = 1.4826  # scale factor making MAD comparable to SD under normality


def log2_tpm(x: np.ndarray) -> np.ndarray:
    """log2(TPM + 1). Named log1p_TPM in the spec by analogy with the common
    log1p transform, but the spec's own formula (section 5) is explicitly
    base-2, not natural log -- do not swap in numpy.log1p (base e)."""
    return np.log2(np.asarray(x, dtype=float) + 1.0)


def tau(x: np.ndarray) -> float:
    """Tau specificity index (0 = broadly expressed, 1 = condition-specific).

    Undefined (NaN), not 0, when there are fewer than 2 valid conditions
    or every value is 0 -- both make max(x) or n-1 degenerate, and
    reporting a fabricated 0 would misleadingly read as "perfectly
    broad".
    """
    values = np.asarray(x, dtype=float)
    values = values[~np.isnan(values)]
    n = len(values)
    if n < 2:
        return np.nan
    peak = values.max()
    if peak <= 0:
        return np.nan
    x_hat = values / peak
    return float(np.sum(1.0 - x_hat) / (n - 1))


def gini(x: np.ndarray) -> float:
    """Gini coefficient of inequality across conditions (secondary specificity
    metric, section 7: optional, benchmarked well by Kryuchkova-Mostacci but
    not mandatory for the first MVP)."""
    values = np.asarray(x, dtype=float)
    values = values[~np.isnan(values)]
    n = len(values)
    if n < 2 or np.all(values == 0):
        return np.nan
    sorted_values = np.sort(values)
    index = np.arange(1, n + 1)
    return float((2 * np.sum(index * sorted_values)) / (n * np.sum(sorted_values)) - (n + 1) / n)


def prevalence(x: np.ndarray, threshold: float) -> float:
    """Fraction of conditions with value >= threshold."""
    values = np.asarray(x, dtype=float)
    values = values[~np.isnan(values)]
    if len(values) == 0:
        return np.nan
    return float(np.mean(values >= threshold))


def abundance_stats(x: np.ndarray) -> dict[str, float]:
    values = np.asarray(x, dtype=float)
    values = values[~np.isnan(values)]
    if len(values) == 0:
        return {"median_TPM": np.nan, "mean_TPM": np.nan, "Q25_TPM": np.nan, "Q75_TPM": np.nan, "Q95_TPM": np.nan, "max_TPM": np.nan}
    return {
        "median_TPM": float(np.median(values)),
        "mean_TPM": float(np.mean(values)),
        "Q25_TPM": float(np.percentile(values, 25)),
        "Q75_TPM": float(np.percentile(values, 75)),
        "Q95_TPM": float(np.percentile(values, 95)),
        "max_TPM": float(np.max(values)),
    }


def variability_stats(x: np.ndarray) -> dict[str, float]:
    """CV, MAD, robust_CV, IQR across conditions.

    CV (SD/mean) blows up as mean -> 0, so robust_CV
    (1.4826 * MAD / median) is the preferred variability statistic for
    lowly-expressed genes -- flagged explicitly rather than silently
    trusted, per the spec's "be careful with CV" instruction.
    """
    values = np.asarray(x, dtype=float)
    values = values[~np.isnan(values)]
    if len(values) < 2:
        return {"CV": np.nan, "MAD": np.nan, "robust_CV": np.nan, "IQR": np.nan}
    mean = np.mean(values)
    median = np.median(values)
    sd = np.std(values, ddof=1)
    mad = np.median(np.abs(values - median))
    cv = float(sd / mean) if mean > 0 else np.nan
    robust_cv = float(_ROBUST_MAD_TO_SD * mad / median) if median > 0 else np.nan
    iqr = float(np.percentile(values, 75) - np.percentile(values, 25))
    return {"CV": cv, "MAD": float(mad), "robust_CV": robust_cv, "IQR": iqr}


def compute_gene_feature_table(
    gene_by_condition: pd.DataFrame,
    prevalence_thresholds: tuple[float, ...] = (0.1, 1.0, 5.0),
) -> pd.DataFrame:
    """Section-8 gene_expression_behavior feature table, one row per gene.

    `gene_by_condition` is the (genes x conditions) median-TPM matrix from
    `matrix.build.pivot_gene_by_condition`. Tau is computed twice (raw TPM
    and log2(TPM+1)) per the spec's transformation-sensitivity requirement
    (section 5) -- neither is silently dropped.
    """
    n_conditions = gene_by_condition.shape[1]
    rows = []
    for gene_id, row in gene_by_condition.iterrows():
        values = row.to_numpy(dtype=float)
        valid = values[~np.isnan(values)]
        n_detected = int(np.sum(valid > 0))

        record: dict[str, object] = {
            "gene": gene_id,
            "n_conditions": n_conditions,
            "n_detected_conditions": n_detected,
        }
        record.update(abundance_stats(values))
        for t in prevalence_thresholds:
            label = str(int(t)) if float(t).is_integer() else str(t)
            record[f"prevalence_TPM_{label}"] = prevalence(values, t)
        record.update(variability_stats(values))
        record["Tau_raw"] = tau(values)
        record["Tau_log1p"] = tau(log2_tpm(values))
        record["Gini_raw"] = gini(values)

        if len(valid) > 0:
            max_idx = int(np.nanargmax(values))
            record["max_expression_condition"] = gene_by_condition.columns[max_idx]
            record["max_expression_TPM"] = float(values[max_idx])
            detected = row[row > 0]
            if len(detected) > 0:
                min_detected_idx = detected.idxmin()
                record["min_detected_condition"] = min_detected_idx
                record["min_detected_TPM"] = float(detected.loc[min_detected_idx])
            else:
                record["min_detected_condition"] = None
                record["min_detected_TPM"] = np.nan
        else:
            record["max_expression_condition"] = None
            record["max_expression_TPM"] = np.nan
            record["min_detected_condition"] = None
            record["min_detected_TPM"] = np.nan

        rows.append(record)

    return pd.DataFrame(rows).set_index("gene")
