"""Gene-centric Tsallis entropy / Hill numbers -- SECONDARY, EXPLORATORY module.

This is explicitly NOT an established gene-classification method. The
primary reference (Derian et al., "The Tsallis generalized entropy
enhances the interpretation of transcriptomics datasets", PLOS ONE
17(4):e0266618, 2022, doi:10.1371/journal.pone.0266618) uses generalized
entropy to characterize whole transcriptomic profiles and groups of
profiles, not individual genes across conditions -- our per-gene
application here is this project's own exploratory adaptation and must
not be described as literature-validated. It exists to test one
question: does the q-spectrum add information beyond Tau/prevalence/
variability, not to replace them (see analysis/entropy/ and
PROJECT_MASTER_SPEC.md section 37, Milestone 10).

q is a sensitivity parameter, not a biological constant: low q up-weights
the low-abundance tail, high q is increasingly dominated by the
strongest-expression conditions. There is no "optimal q" selected here.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

__all__ = [
    "gene_proportions",
    "shannon_entropy",
    "tsallis_entropy",
    "hill_number",
    "q_spectrum",
    "compute_entropy_feature_table",
]

DEFAULT_QS: tuple[float, ...] = (0.5, 1.0, 2.0, 3.0, 4.0)


def gene_proportions(x: np.ndarray) -> np.ndarray:
    """p_gc = TPM_gc / sum_c(TPM_gc) for one gene across conditions.

    NaN-filled if the gene has zero total expression across every
    condition (undefined distribution, not a fabricated uniform one).
    """
    values = np.asarray(x, dtype=float)
    values = np.where(np.isnan(values), 0.0, values)
    total = values.sum()
    if total <= 0:
        return np.full_like(values, np.nan)
    return values / total


def shannon_entropy(p: np.ndarray) -> float:
    """S_1 = -sum(p * ln(p)), with the 0*ln(0) = 0 convention."""
    p = np.asarray(p, dtype=float)
    if np.any(np.isnan(p)):
        return np.nan
    nonzero = p[p > 0]
    return float(-np.sum(nonzero * np.log(nonzero)))


def tsallis_entropy(p: np.ndarray, q: float) -> float:
    """S_q = (1 - sum(p^q)) / (q - 1) for q != 1; Shannon limit at q == 1."""
    p = np.asarray(p, dtype=float)
    if np.any(np.isnan(p)):
        return np.nan
    if np.isclose(q, 1.0):
        return shannon_entropy(p)
    return float((1.0 - np.sum(p**q)) / (q - 1.0))


def hill_number(p: np.ndarray, q: float) -> float:
    """Effective diversity D_q = (sum p^q)^(1/(1-q)) for q != 1; D_1 = exp(S_1).

    Preferred over S_q for biological interpretation (section 20 of the
    classification spec): D_q reads directly as an "effective number of
    conditions" the gene's expression is spread across.
    """
    p = np.asarray(p, dtype=float)
    if np.any(np.isnan(p)):
        return np.nan
    if np.isclose(q, 1.0):
        return float(np.exp(shannon_entropy(p)))
    s = np.sum(p**q)
    if s <= 0:
        return np.nan
    return float(s ** (1.0 / (1.0 - q)))


def q_spectrum(x: np.ndarray, qs: tuple[float, ...] = DEFAULT_QS) -> dict[float, float]:
    """{q: D_q} for one gene's raw TPM vector across conditions."""
    p = gene_proportions(x)
    return {q: hill_number(p, q) for q in qs}


def compute_entropy_feature_table(
    gene_by_condition: pd.DataFrame,
    qs: tuple[float, ...] = DEFAULT_QS,
) -> pd.DataFrame:
    """One row per gene: D_q for each q in `qs`, plus Shannon S_1.

    Mirrors `matrix.stats.compute_gene_feature_table`'s per-gene-row shape
    so the two tables join cleanly on `gene` for the Tau-vs-Dq comparison
    (spec section 21).
    """
    rows = []
    for gene_id, row in gene_by_condition.iterrows():
        values = row.to_numpy(dtype=float)
        p = gene_proportions(values)
        record: dict[str, object] = {"gene": gene_id, "Shannon_S1": shannon_entropy(p)}
        for q in qs:
            key = f"D_{q}".replace(".0", "") if float(q).is_integer() else f"D_{q}"
            record[key] = hill_number(p, q)
        rows.append(record)
    return pd.DataFrame(rows).set_index("gene")
