"""End-to-end BASE-model gene classification (spec sections 11-13), reusable
outside the notebook.

This is a faithful extraction of the decisions made and validated in
`notebooks/gene_expression_classification.ipynb` (Sections 11, 13, 24):
KMeans over the four standardized BASE features
(`clustering.features.BASE_FEATURE_COLUMNS`), k selected by silhouette
score over k=2..10, and the same cautious, legible, threshold-based
`biological_label` rule -- not a black-box classifier, so every label can
be audited against the printed cluster centroids.

Deliberately NOT reproduced here (stays notebook-only, on purpose):
  - the EXTENDED model (BASE + Tsallis/Hill q-spectrum). The notebook's own
    Part B conclusion was that it adds no clustering value and *hurts*
    leave-one-study-out stability -- so the standardized/automated pipeline
    does not pay that cost on every run.
  - cluster stability diagnostics (subsampling/bootstrap/leave-one-study-out
    ARI, dendrograms, pairplots). These are one-time methodological
    validation, not something that needs to re-run every time a study is
    added; re-run the notebook when you want to re-validate stability at a
    materially larger atlas size.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score

from ..entropy.tsallis import DEFAULT_QS, compute_entropy_feature_table
from ..matrix.stats import compute_gene_feature_table
from .features import assemble_base_features, standardize

__all__ = [
    "ClassificationResult",
    "select_k_by_silhouette",
    "fit_kmeans",
    "build_cluster_profile",
    "suggest_label",
    "assign_biological_labels",
    "classify_genes",
]

_MIN_DETECTED_CONDITIONS_FOR_MEDIUM_CONFIDENCE = 3


@dataclass
class ClassificationResult:
    feature_table: pd.DataFrame
    """Established per-gene feature table (abundance/prevalence/variability/Tau/Gini).
    No cluster_id or biological_label -- this is the "established" artifact,
    written on its own before any label is imposed (spec's "do not label
    before examining the data" rule)."""

    entropy_table: pd.DataFrame
    """Per-gene Tsallis/Hill entropy (secondary, exploratory)."""

    cluster_profile: pd.DataFrame
    """One row per cluster_id: n_genes, centroid means, biological_label."""

    k_base: int
    silhouette_scores: pd.Series
    """k -> silhouette score, for k in the range searched."""

    final_table: pd.DataFrame
    """feature_table + entropy_table + cluster_base + biological_label +
    classification_confidence. The production classification artifact."""


def select_k_by_silhouette(
    X: pd.DataFrame, k_range: range = range(2, 11), seed: int = 0
) -> tuple[int, pd.Series]:
    """Pick k by max silhouette score over KMeans fits across `k_range`."""
    scores: dict[int, float] = {}
    for k in k_range:
        labels = KMeans(n_clusters=k, n_init=10, random_state=seed).fit_predict(X)
        scores[k] = silhouette_score(X, labels)
    series = pd.Series(scores, name="silhouette")
    return int(series.idxmax()), series


def fit_kmeans(X: pd.DataFrame, k: int, seed: int = 0) -> pd.Series:
    labels = KMeans(n_clusters=k, n_init=10, random_state=seed).fit_predict(X)
    return pd.Series(labels, index=X.index, name="cluster_base")


def build_cluster_profile(base_features: pd.DataFrame, labels: pd.Series) -> pd.DataFrame:
    """Per-cluster centroid table, sorted highest-to-lowest abundance."""
    profile = (
        base_features.join(labels.rename("cluster_id"))
        .groupby("cluster_id")
        .agg(
            n_genes=("cluster_id", "size"),
            mean_log1p_median_TPM=("log1p_median_TPM", "mean"),
            mean_prevalence_TPM_1=("prevalence_TPM_1", "mean"),
            mean_robust_CV=("robust_CV", "mean"),
            mean_Tau_log1p=("Tau_log1p", "mean"),
        )
    )
    return profile.sort_values("mean_log1p_median_TPM", ascending=False)


def suggest_label(row: pd.Series, profile: pd.DataFrame) -> str:
    """Cautious, legible, data-driven label rule (notebook Section 13, cell 38).

    Thresholds are relative to THIS run's cluster_profile (median/quantile
    of the centroid table), never hard-coded absolutes -- a re-run on a
    larger atlas can shift what counts as "high" without code changes.
    """
    if row["mean_Tau_log1p"] >= 0.6:
        return "condition_specific"
    if (
        row["mean_prevalence_TPM_1"] <= 0.3
        and row["mean_log1p_median_TPM"] <= profile["mean_log1p_median_TPM"].median()
    ):
        return "rarely_expressed"
    if row["mean_robust_CV"] >= profile["mean_robust_CV"].median() and row["mean_Tau_log1p"] < 0.6:
        return "variable_broad"
    if row["mean_log1p_median_TPM"] >= profile["mean_log1p_median_TPM"].quantile(0.66):
        return "constitutive_high"
    return "constitutive_medium"


def assign_biological_labels(profile: pd.DataFrame) -> pd.DataFrame:
    out = profile.copy()
    out["biological_label"] = out.apply(lambda row: suggest_label(row, profile), axis=1)
    return out


def classify_genes(
    gene_by_condition: pd.DataFrame,
    prevalence_thresholds: tuple[float, ...] = (0.1, 1.0, 5.0),
    qs: tuple[float, ...] = DEFAULT_QS,
    k_range: range = range(2, 11),
    seed: int = 0,
) -> ClassificationResult:
    """Run the full BASE-model classification pipeline on a (genes x conditions)
    median-TPM matrix (`matrix.build.pivot_gene_by_condition` output).

    Genes with a NaN in any BASE feature (e.g. Tau undefined for <2 detected
    conditions) are excluded from clustering -- same as the notebook -- and
    simply keep cluster_base/biological_label as NaN in `final_table`
    rather than being dropped from the table entirely.
    """
    feature_table = compute_gene_feature_table(gene_by_condition, prevalence_thresholds)
    entropy_table = compute_entropy_feature_table(gene_by_condition, qs)

    base_features = assemble_base_features(feature_table).dropna()
    X = standardize(base_features)
    k_base, sil_scores = select_k_by_silhouette(X, k_range, seed)
    labels = fit_kmeans(X, k_base, seed)
    profile = assign_biological_labels(build_cluster_profile(base_features, labels))

    final_table = feature_table.join(entropy_table)
    final_table["cluster_base"] = labels
    final_table["biological_label"] = final_table["cluster_base"].map(profile["biological_label"])
    final_table["classification_confidence"] = np.where(
        final_table["n_detected_conditions"] >= _MIN_DETECTED_CONDITIONS_FOR_MEDIUM_CONFIDENCE,
        "medium",
        "low",
    )

    return ClassificationResult(
        feature_table=feature_table,
        entropy_table=entropy_table,
        cluster_profile=profile,
        k_base=k_base,
        silhouette_scores=sil_scores,
        final_table=final_table,
    )
