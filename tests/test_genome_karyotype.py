"""Tests for aoryzae_atlas.genome.karyotype (chromosome expression map binning)."""
from __future__ import annotations

import math

import pandas as pd
import pytest

from aoryzae_atlas.genome.karyotype import bin_gene_expression, chromosome_lengths_by_name
from aoryzae_atlas.reference.genome_fasta import GenomeSequence


def test_chromosome_lengths_by_name():
    seqs = [GenomeSequence("Chr1_A_oryzae_RIB40", 100), GenomeSequence("mito_A_oryzae_RIB40", 10)]
    assert chromosome_lengths_by_name(seqs) == {"Chr1_A_oryzae_RIB40": 100, "mito_A_oryzae_RIB40": 10}


def _genes(rows: list[tuple[str, str, int, int]]) -> pd.DataFrame:
    return pd.DataFrame(rows, columns=["canonical_gene_id", "chromosome", "start", "end"])


def test_bins_cover_whole_chromosome_including_empty_bins():
    genes = _genes([("g1", "Chr1_A_oryzae_RIB40", 100, 200)])
    tpm = pd.Series({"g1": 10.0})
    lengths = {"Chr1_A_oryzae_RIB40": 250}

    out = bin_gene_expression(genes, tpm, lengths, bin_size_bp=100, chromosomes=["Chr1_A_oryzae_RIB40"])

    assert len(out) == 3  # ceil(250/100) = 3 bins, gaps included
    assert list(out["bin_start"]) == [0, 100, 200]
    assert list(out["bin_end"]) == [100, 200, 250]  # last bin clipped to chromosome length
    # g1's midpoint (150) falls in bin 1
    assert out.loc[out["bin_index"] == 1, "n_genes"].iloc[0] == 1
    assert out.loc[out["bin_index"] == 0, "n_genes"].iloc[0] == 0
    assert out.loc[out["bin_index"] == 2, "n_genes"].iloc[0] == 0


def test_empty_bin_tpm_is_nan_not_zero():
    genes = _genes([("g1", "Chr1_A_oryzae_RIB40", 100, 200)])
    tpm = pd.Series({"g1": 10.0})
    lengths = {"Chr1_A_oryzae_RIB40": 200}

    out = bin_gene_expression(genes, tpm, lengths, bin_size_bp=100, chromosomes=["Chr1_A_oryzae_RIB40"])
    empty_bin = out.loc[out["bin_index"] == 0]
    assert math.isnan(empty_bin["mean_TPM"].iloc[0])
    assert math.isnan(empty_bin["log10_mean_TPM"].iloc[0])
    assert empty_bin["n_genes"].iloc[0] == 0


def test_mean_tpm_aggregates_multiple_genes_in_one_bin():
    genes = _genes(
        [
            ("g1", "Chr1_A_oryzae_RIB40", 10, 20),
            ("g2", "Chr1_A_oryzae_RIB40", 30, 40),
        ]
    )
    tpm = pd.Series({"g1": 10.0, "g2": 30.0})
    lengths = {"Chr1_A_oryzae_RIB40": 100}

    out = bin_gene_expression(genes, tpm, lengths, bin_size_bp=100, chromosomes=["Chr1_A_oryzae_RIB40"])
    row = out.iloc[0]
    assert row["n_genes"] == 2
    assert row["mean_TPM"] == 20.0
    assert row["log10_mean_TPM"] == pytest.approx(math.log10(21.0))


def test_n_detected_genes_counts_only_positive_tpm():
    genes = _genes(
        [
            ("g1", "Chr1_A_oryzae_RIB40", 10, 20),
            ("g2", "Chr1_A_oryzae_RIB40", 30, 40),
        ]
    )
    tpm = pd.Series({"g1": 0.0, "g2": 5.0})
    lengths = {"Chr1_A_oryzae_RIB40": 100}

    out = bin_gene_expression(genes, tpm, lengths, bin_size_bp=100, chromosomes=["Chr1_A_oryzae_RIB40"])
    row = out.iloc[0]
    assert row["n_genes"] == 2
    assert row["n_detected_genes"] == 1


def test_genes_on_other_chromosomes_are_excluded():
    genes = _genes(
        [
            ("g1", "Chr1_A_oryzae_RIB40", 10, 20),
            ("g2", "mito_A_oryzae_RIB40", 5, 15),
        ]
    )
    tpm = pd.Series({"g1": 10.0, "g2": 999.0})
    lengths = {"Chr1_A_oryzae_RIB40": 100}

    out = bin_gene_expression(genes, tpm, lengths, bin_size_bp=100, chromosomes=["Chr1_A_oryzae_RIB40"])
    assert out["n_genes"].sum() == 1  # mito gene never entered the working set
