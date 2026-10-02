"""Rule-based expression classes with thresholds derived from the global gene distribution.

No absolute-TPM cut-offs (like "TPM > 100 = high"): every cut-off is a quantile of
the atlas' own distributions, computed at run time and returned as a `Thresholds`
record so a reader can answer "exactly how was this class generated?".

Decision order (each gene gets exactly one class):

 1. Context-Specific  burst-capable gene (reaches, in at least one sample, the *median level of the
                      expressed transcriptome*) whose Tau AND peak concentration are both in the top
                      tail of the burst-capable genes (expression concentrated in few samples)
 2. Rare/Silent       not detected in the typical sample and no strong bursts
 3. Constitutive X    detected in (nearly) every sample and OUTSIDE the high tail (`tail_quantile`) of
                      dispersion and of Tau *relative to genes of the same level tier*; High / Core /
                      Low from level quantiles of E
 4. Broad Variable    expressed in the typical sample and INSIDE the high-dispersion tail of its tier,
                      with no concentration into a few samples (it need not be detected everywhere)
 5. Intermediate      everything else (the honest remainder of a continuum, not a failure to classify)

"Expressed" genes (E) are those whose *sample median* reaches the lowest detection
threshold (0.1 TPM) -- i.e. detected in the typical sample. Dispersion is compared within
level tiers because log-scale dispersion is mechanically compressed at low expression. The 0.80
tail quantile is supported by the data's own structure: a 2-component mixture on MAD among broadly
expressed genes puts ~20% of genes in a distinct high-dispersion mode (printed in the notebook).
"""
from __future__ import annotations

from dataclasses import asdict, dataclass

import numpy as np
import pandas as pd

__all__ = [
    "CLASS_ORDER",
    "ClassParams",
    "Thresholds",
    "derive_thresholds",
    "level_tiers",
    "assign_classes",
    "perturbed_params",
    "class_stability",
    "class_agreement",
]

CLASS_ORDER: tuple[str, ...] = (
    "Constitutive High",
    "Constitutive Core",
    "Constitutive Low",
    "Broad Variable",
    "Context-Specific",
    "Rare/Silent",
    "Intermediate",
)


@dataclass(frozen=True)
class ClassParams:
    detect_tpm: float = 0.1
    level_quantiles: tuple[float, float] = (0.20, 0.80)
    burst_quantile: float = 0.50
    prevalence_quantile: float = 0.25
    specific_quantile: float = 0.75
    tail_quantile: float = 0.80


@dataclass(frozen=True)
class Thresholds:
    n_expressed_genes: int
    level_low: float
    level_high: float
    floor_level: float
    floor_tpm: float
    n_burst_capable_genes: int
    tau_specific: float
    peak_specific: float
    prevalence_broad: float
    n_eligible_genes: int

    def as_frame(self) -> pd.DataFrame:
        return pd.DataFrame({"threshold": list(asdict(self).keys()), "value": list(asdict(self).values())})


def _quantile(values: pd.Series, q: float) -> float:
    values = values.dropna()
    return float(values.quantile(q)) if len(values) else float("nan")


def derive_thresholds(metrics: pd.DataFrame, params: ClassParams = ClassParams()) -> Thresholds:
    expressed = metrics["median_TPM"] >= params.detect_tpm
    level_low = _quantile(metrics.loc[expressed, "median_logTPM"], params.level_quantiles[0])
    level_high = _quantile(metrics.loc[expressed, "median_logTPM"], params.level_quantiles[1])
    floor_level = _quantile(metrics.loc[expressed, "median_logTPM"], params.burst_quantile)
    floor_tpm = float(2.0**floor_level - 1.0)

    burst = metrics["max_TPM"] >= floor_tpm
    tau_specific = _quantile(metrics.loc[burst, "Tau"], params.specific_quantile)
    peak_specific = _quantile(metrics.loc[burst, "peak_share_top10pct"], params.specific_quantile)
    prevalence_broad = _quantile(metrics.loc[expressed, "prevalence_TPM_0.1"], params.prevalence_quantile)

    context = burst & (metrics["Tau"] >= tau_specific) & (metrics["peak_share_top10pct"] >= peak_specific)
    eligible = expressed & ~context
    return Thresholds(
        n_expressed_genes=int(expressed.sum()),
        level_low=level_low,
        level_high=level_high,
        floor_level=floor_level,
        floor_tpm=floor_tpm,
        n_burst_capable_genes=int(burst.sum()),
        tau_specific=tau_specific,
        peak_specific=peak_specific,
        prevalence_broad=prevalence_broad,
        n_eligible_genes=int(eligible.sum()),
    )


def level_tiers(metrics: pd.DataFrame, params: ClassParams = ClassParams()) -> pd.Series:
    """Low / Core / High level tier from the Q20/Q80 of the expressed genes; 'Not expressed' otherwise."""
    th = derive_thresholds(metrics, params)
    expressed = metrics["median_TPM"] >= params.detect_tpm
    level = metrics["median_logTPM"]
    tier = np.where(level < th.level_low, "Low", np.where(level >= th.level_high, "High", "Core"))
    return pd.Series(np.where(expressed, tier, "Not expressed"), index=metrics.index, name="level_tier")


def assign_classes(metrics: pd.DataFrame, params: ClassParams = ClassParams()) -> pd.Series:
    """Categorical class per gene (ordered as CLASS_ORDER)."""
    th = derive_thresholds(metrics, params)
    expressed = metrics["median_TPM"] >= params.detect_tpm
    level = metrics["median_logTPM"]

    burst = metrics["max_TPM"] >= th.floor_tpm
    context = burst & (metrics["Tau"] >= th.tau_specific) & (metrics["peak_share_top10pct"] >= th.peak_specific)
    rare = ~expressed & ~context & (metrics["P90_TPM"] < th.floor_tpm)
    broad = expressed & (metrics["prevalence_TPM_0.1"] >= th.prevalence_broad)
    eligible = expressed & ~context

    tier = pd.Series(
        np.where(level < th.level_low, "Low", np.where(level >= th.level_high, "High", "Core")),
        index=metrics.index,
    )
    tier_peers = tier.where(eligible)
    mad_pct = metrics["MAD_logTPM"].where(eligible).groupby(tier_peers).rank(pct=True)
    iqr_pct = metrics["IQR_logTPM"].where(eligible).groupby(tier_peers).rank(pct=True)
    tau_pct = metrics["Tau"].where(eligible).groupby(tier_peers).rank(pct=True)
    dispersion_pct = (mad_pct + iqr_pct) / 2.0

    constitutive = eligible & broad & (dispersion_pct < params.tail_quantile) & (tau_pct < params.tail_quantile)
    variable = eligible & (dispersion_pct >= params.tail_quantile) & ~constitutive

    labels = pd.Series("Intermediate", index=metrics.index, dtype=object)
    labels[variable] = "Broad Variable"
    for tier_name in ("Low", "Core", "High"):
        labels[constitutive & (tier == tier_name)] = f"Constitutive {tier_name}"
    labels[rare] = "Rare/Silent"
    labels[context] = "Context-Specific"
    return pd.Series(pd.Categorical(labels, categories=CLASS_ORDER, ordered=True), index=metrics.index, name="expression_class")


def perturbed_params(base: ClassParams = ClassParams()) -> list[ClassParams]:
    """Single-knob perturbations around `base` (+/- 5-10 percentile points) used for the stability check."""
    lo, hi = base.level_quantiles
    out = [
        ClassParams(**{**asdict(base), "level_quantiles": (round(lo - 0.05, 2), round(hi + 0.05, 2))}),
        ClassParams(**{**asdict(base), "level_quantiles": (round(lo + 0.05, 2), round(hi - 0.05, 2))}),
    ]
    for field, delta in (
        ("burst_quantile", 0.10),
        ("prevalence_quantile", 0.10),
        ("specific_quantile", 0.10),
        ("tail_quantile", 0.10),
    ):
        value = getattr(base, field)
        out.append(ClassParams(**{**asdict(base), field: round(value - delta, 2)}))
        out.append(ClassParams(**{**asdict(base), field: round(value + delta, 2)}))
    return out


def class_stability(metrics: pd.DataFrame, base: ClassParams = ClassParams()) -> tuple[pd.Series, pd.DataFrame]:
    """Per-gene fraction of single-knob perturbations that keep the base class, plus a per-perturbation summary."""
    base_classes = assign_classes(metrics, base).astype(str)
    agree = pd.DataFrame(index=metrics.index)
    summary_rows = []
    for i, params in enumerate(perturbed_params(base)):
        perturbed = assign_classes(metrics, params).astype(str)
        agree[i] = perturbed == base_classes
        changed = {k: v for k, v in asdict(params).items() if v != asdict(base)[k]}
        summary_rows.append({"perturbation": str(changed), "fraction_genes_unchanged": float(agree[i].mean())})
    return agree.mean(axis=1).rename("class_stability"), pd.DataFrame(summary_rows)


def class_agreement(a: pd.Series, b: pd.Series) -> float:
    """Fraction of genes (present in both) assigned the same class."""
    common = a.index.intersection(b.index)
    if len(common) == 0:
        return float("nan")
    return float((a.loc[common].astype(str) == b.loc[common].astype(str)).mean())
