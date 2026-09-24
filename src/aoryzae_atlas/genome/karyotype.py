"""Bin per-gene expression into fixed-size genomic windows per chromosome,
for a karyotype-style whole-genome expression map (TODO.md "chromosome-wide
TPM abundance map" feature idea).

Aggregation unit is a fixed-size window, not per-gene: gene density varies
>2x across RIB40's 8 chromosomes, so per-gene coloring looks uneven/gappy,
while fixed windows read as "regions" -- the shape the feature was actually
described in. Bin size is a parameter, not a hard-coded constant (the
feature idea explicitly wanted this tunable, same spirit as `config/
qc.yaml`'s multi-threshold TPM detection philosophy).
"""
from __future__ import annotations

import math

import pandas as pd

from ..reference.genome_fasta import GenomeSequence

__all__ = [
    "NUCLEAR_CHROMOSOMES",
    "DEFAULT_BIN_SIZE_BP",
    "chromosome_lengths_by_name",
    "bin_gene_expression",
]

NUCLEAR_CHROMOSOMES = [f"Chr{i}_A_oryzae_RIB40" for i in range(1, 9)]
"""RIB40's 8 nuclear chromosomes, in karyotype order. Excludes the 3
unplaced contigs and the mitochondrial genome (1-16 genes each -- too
sparse to render meaningfully alongside an 8-chromosome view; see TODO.md).
"""

DEFAULT_BIN_SIZE_BP = 100_000


def chromosome_lengths_by_name(sequences: list[GenomeSequence]) -> dict[str, int]:
    return {s.name: s.length for s in sequences}


def bin_gene_expression(
    genes: pd.DataFrame,
    median_tpm: pd.Series,
    chromosome_lengths: dict[str, int],
    bin_size_bp: int = DEFAULT_BIN_SIZE_BP,
    chromosomes: list[str] = NUCLEAR_CHROMOSOMES,
) -> pd.DataFrame:
    """One row per (chromosome, bin_index): bin_start, bin_end, n_genes,
    n_detected_genes, mean_TPM, log10_mean_TPM.

    `genes` needs canonical_gene_id/chromosome/start/end columns (the
    `genes` DuckDB table). `median_tpm` is a Series indexed by
    canonical_gene_id -- a whole-atlas representative abundance per gene
    (`matrix.stats.compute_gene_feature_table`'s median_TPM column: median
    across every curated condition, so this reflects the full atlas, not
    one sample or condition).

    Gene -> bin assignment uses the gene's midpoint, not full-overlap
    splitting: genes are typically far smaller than bin_size_bp (median
    gene length is on the order of 1-2kb vs. a 50kb default bin), so
    midpoint assignment introduces negligible edge error and avoids
    double-counting genes straddling a bin boundary.

    A bin with n_genes == 0 (an annotation gap -- centromeric/telomeric
    regions, or just a sparser stretch) keeps mean_TPM/log10_mean_TPM as
    NaN: "nothing annotated here" is a different fact from "annotated but
    undetected" and must render distinctly, never as the bottom of the
    same color scale.
    """
    working = genes[genes["chromosome"].isin(chromosomes)].copy()
    working["mid"] = (working["start"].astype("int64") + working["end"].astype("int64")) // 2
    working["tpm"] = working["canonical_gene_id"].map(median_tpm)

    rows: list[dict[str, object]] = []
    for chrom in chromosomes:
        length = chromosome_lengths.get(chrom)
        if length is None:
            continue
        n_bins = max(1, math.ceil(length / bin_size_bp))

        chrom_genes = working[working["chromosome"] == chrom].copy()
        chrom_genes["bin_index"] = (chrom_genes["mid"] // bin_size_bp).clip(upper=n_bins - 1).astype(int)

        n_genes_by_bin = chrom_genes.groupby("bin_index").size()
        mean_tpm_by_bin = chrom_genes.groupby("bin_index")["tpm"].mean()
        n_detected_by_bin = chrom_genes.groupby("bin_index")["tpm"].apply(lambda s: int((s > 0).sum()))

        for i in range(n_bins):
            bin_start = i * bin_size_bp
            bin_end = min(length, bin_start + bin_size_bp)
            n_genes = int(n_genes_by_bin.get(i, 0))
            raw_mean = mean_tpm_by_bin.get(i)
            mean_tpm = float(raw_mean) if n_genes > 0 and raw_mean is not None and not pd.isna(raw_mean) else float("nan")
            rows.append(
                {
                    "chromosome": chrom,
                    "bin_index": i,
                    "bin_start": bin_start,
                    "bin_end": bin_end,
                    "n_genes": n_genes,
                    "n_detected_genes": int(n_detected_by_bin.get(i, 0)),
                    "mean_TPM": mean_tpm,
                    "log10_mean_TPM": math.log10(mean_tpm + 1.0) if not math.isnan(mean_tpm) else float("nan"),
                }
            )
    return pd.DataFrame(rows)
