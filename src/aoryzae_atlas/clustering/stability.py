"""Cluster-stability primitives (spec section 12: silhouette, bootstrap,
subsampling, leave-one-study-out). The perturbation itself (drop one
study's conditions, refit, get new labels) is orchestrated in the
notebook using `matrix.build`; this module only scores agreement between
two label sets so that scoring logic is written once and tested once.
"""
from __future__ import annotations

import pandas as pd
from sklearn.metrics import adjusted_rand_score

__all__ = ["cluster_label_agreement"]


def cluster_label_agreement(labels_a: pd.Series, labels_b: pd.Series) -> float:
    """Adjusted Rand Index between two clusterings, restricted to genes present in both.

    Perturbed runs (e.g. leave-one-study-out) can drop genes that become
    all-NaN once certain conditions are removed, so the two label sets
    won't always share an index -- comparing only the intersection is the
    correct stability question ("do genes clustered in both runs still
    agree?"), not an error to silence.

    Returns NaN if fewer than 2 genes are shared (ARI undefined there).
    """
    common = labels_a.index.intersection(labels_b.index)
    if len(common) < 2:
        return float("nan")
    return float(adjusted_rand_score(labels_a.loc[common], labels_b.loc[common]))
