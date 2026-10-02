import type { ExpressionClass, ExpressionRankRow, Gene } from "../data/types";

/** Fixed order = identity (never re-sorted by count), per the dataviz rules. */
export const CLASS_ORDER: ExpressionClass[] = [
  "Constitutive High",
  "Constitutive Core",
  "Constitutive Low",
  "Broad Variable",
  "Context-Specific",
  "Rare/Silent",
  "Intermediate",
];

export const CLASS_COLOR_VAR: Record<ExpressionClass, string> = {
  "Constitutive High": "--class-constitutive-high",
  "Constitutive Core": "--class-constitutive-core",
  "Constitutive Low": "--class-constitutive-low",
  "Broad Variable": "--class-broad-variable",
  "Context-Specific": "--class-context-specific",
  "Rare/Silent": "--class-rare-silent",
  Intermediate: "--class-intermediate",
};

export function classColor(cls: ExpressionClass): string {
  return `var(${CLASS_COLOR_VAR[cls]})`;
}

/** One line per class, written for biologists (shown in tooltips / legend). */
export const CLASS_DESCRIPTION: Record<ExpressionClass, string> = {
  "Constitutive High": "Highly expressed and steady in nearly every sample.",
  "Constitutive Core": "Mid-level, steady expression across the whole atlas.",
  "Constitutive Low": "Low but consistently detectable, steady expression.",
  "Broad Variable": "Detected almost everywhere but swings widely between samples.",
  "Context-Specific": "Concentrated in a few samples (statistical, not a proven condition).",
  "Rare/Silent": "Essentially never detected.",
  Intermediate: "Between the other classes — the gray zone of a continuum.",
};

/** The six independent orderings (a gene's rank is 1 = best on each). */
export type RankOrdering = "global" | "expressed" | "stable" | "variable" | "specific" | "rarest";

export interface OrderingDef {
  key: RankOrdering;
  label: string;
  description: string;
  rank: (row: ExpressionRankRow) => number;
  /** Short, unit-bearing value shown at the end of each row (a bar would be ~full for every top gene). */
  value: (row: ExpressionRankRow) => string;
}

const pct = (score: number): string => String(Math.round(score * 100));

export const ORDERINGS: OrderingDef[] = [
  {
    key: "global",
    label: "Most constitutive",
    description: "High level, stable and detected everywhere (geometric mean of the three scores).",
    rank: (r) => r.global_rank,
    value: (r) => `level ${pct(r.level_score)} · stable ${pct(r.stability_score)}`,
  },
  {
    key: "expressed",
    label: "Most expressed",
    description: "Highest typical (median) expression across all samples.",
    rank: (r) => r.rank_most_expressed,
    value: (r) => `${r.median_TPM >= 10 ? Math.round(r.median_TPM).toLocaleString("en-US") : r.median_TPM.toFixed(1)} TPM`,
  },
  {
    key: "stable",
    label: "Most stable",
    description: "Low dispersion, low specificity and high prevalence together.",
    rank: (r) => r.rank_most_stable,
    value: (r) => `stability ${pct(r.stability_score)}`,
  },
  {
    key: "variable",
    label: "Most variable",
    description: "Largest spread (MAD of log2 TPM) between samples.",
    rank: (r) => r.rank_most_variable,
    value: (r) => `MAD ${r.MAD_logTPM.toFixed(2)}`,
  },
  {
    key: "specific",
    label: "Most specific",
    description: "Expression concentrated in the fewest samples (Tau + peak share); real bursts outrank sub-TPM blips.",
    rank: (r) => r.rank_most_specific,
    value: (r) => `Tau ${r.Tau === null ? "–" : r.Tau.toFixed(2)}`,
  },
  {
    key: "rarest",
    label: "Rarest",
    description: "Lowest prevalence across the atlas.",
    rank: (r) => r.rank_rarest,
    value: (r) => `detected in ${Math.round(r.prevalence_TPM_1 * 100)}%`,
  },
];

export function flagList(row: ExpressionRankRow): string[] {
  return row.quality_flags ? row.quality_flags.split(";").filter(Boolean) : [];
}

export const FLAG_TEXT: Record<string, string> = {
  possible_study_effect: "Most of its highest expression comes from a single study",
  possible_strain_effect: "Most of its highest expression comes from a single strain",
  low_sample_support: "Class rests on very few samples",
  borderline_class: "Class changes under small threshold changes",
};

export interface ChromosomeComposition {
  chromosome: string;
  total: number;
  counts: Record<ExpressionClass, number>;
}

/** Genes per chromosome x class, in the same chromosome order as the genome map. */
export function chromosomeComposition(
  genes: Gene[],
  byGene: Map<string, ExpressionRankRow>,
  chromosomeOrder: string[],
): ChromosomeComposition[] {
  const table = new Map<string, ChromosomeComposition>();
  for (const chromosome of chromosomeOrder) {
    table.set(chromosome, {
      chromosome,
      total: 0,
      counts: Object.fromEntries(CLASS_ORDER.map((c) => [c, 0])) as Record<ExpressionClass, number>,
    });
  }
  for (const gene of genes) {
    const entry = table.get(gene.chromosome);
    const row = byGene.get(gene.canonical_gene_id);
    if (!entry || !row) continue;
    entry.total += 1;
    entry.counts[row.expression_class] += 1;
  }
  return chromosomeOrder.map((c) => table.get(c)!).filter((entry) => entry.total > 0);
}
