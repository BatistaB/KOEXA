import type { Gene } from "../data/types";

/**
 * Only ~5% of the real RIB40 catalog has a curated short symbol (see
 * scripts/export_gene_catalog.py) — the rest fall back to the UniProt
 * protein name, then the bare canonical ID. Never italicize a fallback:
 * italics is a symbol-nomenclature convention, wrong for an ID or a full
 * protein-name string.
 */
export function primaryGeneLabel(gene: Gene): string {
  return gene.gene_symbol ?? gene.gene_name ?? gene.canonical_gene_id;
}

export function isSymbolicLabel(gene: Gene): boolean {
  return gene.gene_symbol !== null;
}

export function truncateLabel(value: string, max = 16): string {
  return value.length > max ? `${value.slice(0, max - 1)}…` : value;
}

/** Genomic coordinates are 1-based inclusive, so length = end - start + 1. */
export function geneLengthBp(gene: Gene): number {
  return gene.end - gene.start + 1;
}

export function formatBp(bp: number): string {
  return `${bp.toLocaleString("en-US")} bp`;
}
