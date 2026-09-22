"""Tests for aoryzae_atlas.entropy.tsallis (Milestone 10, secondary/exploratory)."""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from aoryzae_atlas.entropy.tsallis import (
    compute_entropy_feature_table,
    gene_proportions,
    hill_number,
    q_spectrum,
    shannon_entropy,
    tsallis_entropy,
)


def test_gene_proportions_sum_to_one():
    p = gene_proportions(np.array([1.0, 2.0, 3.0, 4.0]))
    assert p.sum() == pytest.approx(1.0)


def test_gene_proportions_undefined_for_all_zero():
    p = gene_proportions(np.array([0.0, 0.0, 0.0]))
    assert np.all(np.isnan(p))


def test_shannon_entropy_uniform_equals_ln_n():
    p = gene_proportions(np.array([1.0, 1.0, 1.0, 1.0]))
    assert shannon_entropy(p) == pytest.approx(np.log(4))


def test_shannon_entropy_degenerate_is_zero():
    p = gene_proportions(np.array([0.0, 0.0, 100.0]))
    assert shannon_entropy(p) == pytest.approx(0.0)


def test_hill_number_uniform_equals_n_for_any_q():
    p = gene_proportions(np.array([5.0, 5.0, 5.0, 5.0]))
    for q in (0.5, 1.0, 2.0, 3.0, 4.0):
        assert hill_number(p, q) == pytest.approx(4.0), f"q={q}"


def test_hill_number_degenerate_equals_one_for_any_q():
    p = gene_proportions(np.array([0.0, 0.0, 0.0, 100.0]))
    for q in (0.5, 1.0, 2.0, 3.0, 4.0):
        assert hill_number(p, q) == pytest.approx(1.0), f"q={q}"


def test_hill_number_q1_matches_exp_shannon():
    p = gene_proportions(np.array([1.0, 3.0, 6.0]))
    assert hill_number(p, 1.0) == pytest.approx(np.exp(shannon_entropy(p)))


def test_tsallis_entropy_q1_matches_shannon_limit():
    p = gene_proportions(np.array([2.0, 3.0, 5.0]))
    assert tsallis_entropy(p, 1.0) == pytest.approx(shannon_entropy(p))


def test_q_spectrum_returns_all_requested_qs():
    spectrum = q_spectrum(np.array([1.0, 2.0, 3.0]), qs=(0.5, 1.0, 2.0))
    assert set(spectrum.keys()) == {0.5, 1.0, 2.0}
    assert all(not np.isnan(v) for v in spectrum.values())


def test_compute_entropy_feature_table_shape():
    matrix = pd.DataFrame(
        {"condA": [10.0, 0.0], "condB": [10.0, 0.0], "condC": [10.0, 100.0]},
        index=["geneFlat", "geneSpecific"],
    )
    table = compute_entropy_feature_table(matrix, qs=(1.0, 2.0))
    assert table.loc["geneFlat", "D_2"] == pytest.approx(3.0)
    assert table.loc["geneSpecific", "D_2"] == pytest.approx(1.0)
