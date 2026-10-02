"""Continuous expression scores and rank orderings (never collapsed into one number).

Every score is a percentile rank in (0, 1] over the genes in the table, so
scores are comparable across metrics and carry no absolute-TPM assumption.
The components stay as separate columns; `constitutive_score` /
`global_expression_rank` is only one *ordering* ("most constitutively
expressed"), and the other orderings are provided alongside it.

Undefined Tau / peak concentration (a gene never expressed anywhere) counts as
"no specificity evidence" (0) rather than being dropped, so silent genes cannot
rise to the top of the specificity ranking.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

__all__ = ["pct_rank", "compute_scores"]


def pct_rank(values: pd.Series) -> pd.Series:
    """Percentile rank in (0, 1]: average rank / n. Ties share their average rank."""
    return values.rank(method="average") / values.notna().sum()


def compute_scores(metrics: pd.DataFrame) -> pd.DataFrame:
    """Level / prevalence / stability / specificity scores + ordering columns.

    expression_level_score        rank of median_logTPM
    expression_prevalence_score   rank of mean(prevalence at 0.1, 1, 5 TPM)
    expression_stability_score    geometric mean of [prevalence score, low-MAD, low-IQR, low-Tau]
                                  ranks -- a gene is stable only if all four agree, so a silent
                                  gene (zero dispersion but zero prevalence) cannot score as stable
    expression_specificity_score  mean of the Tau rank and the peak-concentration rank
    constitutive_score            geometric mean of level, stability and prevalence scores
    """
    out = pd.DataFrame(index=metrics.index)

    prevalence_cols = [c for c in metrics.columns if c.startswith("prevalence_TPM_")]
    prevalence_composite = metrics[prevalence_cols].mean(axis=1)
    tau = metrics["Tau"].fillna(0.0)
    peak = metrics["peak_share_top10pct"].fillna(0.0)

    out["expression_level_score"] = pct_rank(metrics["median_logTPM"])
    out["expression_prevalence_score"] = pct_rank(prevalence_composite)

    stability_components = np.vstack(
        [
            out["expression_prevalence_score"].to_numpy(),
            pct_rank(-metrics["MAD_logTPM"]).to_numpy(),
            pct_rank(-metrics["IQR_logTPM"]).to_numpy(),
            pct_rank(-tau).to_numpy(),
        ]
    )
    out["expression_stability_score"] = np.exp(np.log(stability_components).mean(axis=0))

    out["expression_specificity_score"] = (pct_rank(tau) + pct_rank(peak)) / 2.0

    out["constitutive_score"] = np.exp(
        np.log(
            np.vstack(
                [
                    out["expression_level_score"].to_numpy(),
                    out["expression_stability_score"].to_numpy(),
                    out["expression_prevalence_score"].to_numpy(),
                ]
            )
        ).mean(axis=0)
    )

    out["global_expression_rank"] = out["constitutive_score"].rank(ascending=False, method="min").astype(int)
    out["rank_most_expressed"] = metrics["median_logTPM"].rank(ascending=False, method="min").astype(int)
    out["rank_most_stable"] = out["expression_stability_score"].rank(ascending=False, method="min").astype(int)
    out["rank_most_variable"] = metrics["MAD_logTPM"].rank(ascending=False, method="min").astype(int)
    # Most specific = highest specificity score; ties (many genes sit at Tau = peak share = 1 on a single noisy
    # sample) are broken by the size of the burst, so real bursts outrank sub-TPM blips.
    spec_order = np.lexsort((-metrics["max_TPM"].to_numpy(), -out["expression_specificity_score"].to_numpy()))
    specific_rank = np.empty(len(spec_order), dtype=int)
    specific_rank[spec_order] = np.arange(1, len(spec_order) + 1)
    out["rank_most_specific"] = specific_rank
    # Rarest = lowest prevalence, ties broken by lowest median level (many genes tie at prevalence 0).
    order = np.lexsort((metrics["median_logTPM"].to_numpy(), prevalence_composite.to_numpy()))
    rarest_rank = np.empty(len(order), dtype=int)
    rarest_rank[order] = np.arange(1, len(order) + 1)
    out["rank_rarest"] = rarest_rank
    return out
