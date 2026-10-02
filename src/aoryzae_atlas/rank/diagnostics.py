"""Heterogeneity diagnostics: quality flags, never automatic exclusion.

The atlas mixes studies, laboratories and strains by design; nothing here
re-analyses individual studies. `group_dominance` asks, per gene, whether its
*high-expression samples* (TPM at/above the gene's own P90 and > 0) come
disproportionately from a single group (a study or a strain), tested against
the hypergeometric expectation given each group's share of all samples.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy.stats import hypergeom

__all__ = ["DOMINANCE_MIN", "ENRICHMENT_MIN", "DOMINANCE_Q_MAX", "benjamini_hochberg", "group_dominance", "dominance_flag", "build_quality_flags"]


# Flag calibration: only the extreme cases are flagged. The atlas is strongly structured by study/strain, so a
# plain "majority of high samples" rule would flag most genes; requiring >= 2.5x the group's share of all samples
# keeps a group that merely holds most samples from being flagged by size alone.
DOMINANCE_MIN = 0.8
ENRICHMENT_MIN = 2.5
DOMINANCE_Q_MAX = 0.05


def benjamini_hochberg(p_values: np.ndarray) -> np.ndarray:
    """BH-adjusted q-values; NaN p-values stay NaN."""
    p = np.asarray(p_values, dtype=float)
    q = np.full_like(p, np.nan)
    valid = ~np.isnan(p)
    pv = p[valid]
    order = np.argsort(pv)
    ranked = pv[order] * len(pv) / np.arange(1, len(pv) + 1)
    ranked = np.minimum.accumulate(ranked[::-1])[::-1]
    adjusted = np.empty_like(pv)
    adjusted[order] = np.clip(ranked, 0.0, 1.0)
    q[valid] = adjusted
    return q


def group_dominance(tpm: pd.DataFrame, groups: pd.Series, high_quantile: float = 0.90) -> pd.DataFrame:
    """Per-gene dominance of one group (study/strain) among the gene's high-expression samples.

    `groups` maps each column of `tpm` (sample) to its group label.
    Returns dominance (share of high samples from the top group), dominant_group,
    enrichment (dominance / that group's share of all samples) and a BH q-value
    from the hypergeometric upper tail.
    """
    groups = groups.reindex(tpm.columns)
    if groups.isna().any():
        raise ValueError("every TPM column needs a group label")

    x = tpm.to_numpy(dtype=float)
    p_high = (np.percentile if not np.isnan(x).any() else np.nanpercentile)(x, high_quantile * 100, axis=1)
    high = (x >= p_high[:, None]) & (x > 0)

    labels = pd.Index(sorted(groups.unique()))
    one_hot = np.column_stack([(groups.to_numpy() == g).astype(float) for g in labels])
    counts = high.astype(float) @ one_hot
    n_high = counts.sum(axis=1)
    group_sizes = one_hot.sum(axis=0)
    n_total = x.shape[1]

    top = counts.argmax(axis=1)
    top_count = counts[np.arange(len(counts)), top]
    with np.errstate(divide="ignore", invalid="ignore"):
        dominance = top_count / n_high
    dominance[n_high == 0] = np.nan
    expected_share = group_sizes[top] / n_total
    with np.errstate(divide="ignore", invalid="ignore"):
        enrichment = dominance / expected_share

    p_value = np.where(
        n_high > 0,
        hypergeom.sf(top_count - 1, n_total, group_sizes[top], np.maximum(n_high, 1)),
        np.nan,
    )
    out = pd.DataFrame(
        {
            "dominance": dominance,
            "dominant_group": labels[top].to_numpy(),
            "dominance_enrichment": enrichment,
            "dominance_q": benjamini_hochberg(p_value),
        },
        index=tpm.index,
    )
    out.loc[n_high == 0, "dominant_group"] = None
    return out


def dominance_flag(
    dominance: pd.DataFrame,
    dominance_min: float = DOMINANCE_MIN,
    enrichment_min: float = ENRICHMENT_MIN,
    q_max: float = DOMINANCE_Q_MAX,
) -> pd.Series:
    """True where a gene's high-expression samples come (almost) all from one group, far above that group's share."""
    return (
        (dominance["dominance"] >= dominance_min)
        & (dominance["dominance_enrichment"] >= enrichment_min)
        & (dominance["dominance_q"] < q_max)
    )


def build_quality_flags(flags: dict[str, pd.Series]) -> pd.Series:
    """Semicolon-joined names of the flags that are True per gene ('' when none)."""
    frame = pd.DataFrame(flags).fillna(False).astype(bool)
    return frame.apply(lambda row: ";".join(name for name, hit in row.items() if hit), axis=1).rename("quality_flags")
