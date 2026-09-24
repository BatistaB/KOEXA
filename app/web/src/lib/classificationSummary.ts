import type { BiologicalLabel, GeneClassification } from "../data/types";

export interface ClassificationSlice {
  key: BiologicalLabel | "unclassified";
  label: string;
  count: number;
  fraction: number;
  color: string;
}

/**
 * Fixed slot order for biological_label (categorical identity, per the
 * dataviz skill: fixed hue order, never cycled/reassigned by what happens
 * to be present in one run). Only 2 of these 5 labels are populated at
 * the atlas's current pilot scale (K_BASE=2) -- the others light up
 * automatically once more studies/conditions let clustering resolve more
 * than 2 groups, with no code change needed here.
 */
const LABEL_ORDER: BiologicalLabel[] = [
  "constitutive_high",
  "constitutive_medium",
  "variable_broad",
  "condition_specific",
  "rarely_expressed",
];

const LABEL_TEXT: Record<BiologicalLabel, string> = {
  constitutive_high: "Constitutive · high",
  constitutive_medium: "Constitutive · medium",
  variable_broad: "Variable, broadly expressed",
  condition_specific: "Condition-specific",
  rarely_expressed: "Rarely expressed",
};

const LABEL_COLOR: Record<BiologicalLabel, string> = {
  constitutive_high: "var(--series-1)",
  constitutive_medium: "var(--series-2)",
  variable_broad: "var(--series-3)",
  condition_specific: "var(--series-4)",
  rarely_expressed: "var(--series-5)",
};

/** Genes with no biological_label (fewer than 2 detected conditions --
 * Tau undefined, excluded from clustering) get a muted neutral slice, not
 * a 6th vivid categorical hue: it isn't a biological category, it's "not
 * enough data yet". */
const UNCLASSIFIED_COLOR = "var(--border-default)";

export function summarizeClassification(classification: Map<string, GeneClassification>): ClassificationSlice[] {
  const counts = new Map<string, number>();
  let total = 0;
  for (const entry of classification.values()) {
    const key = entry.biological_label ?? "unclassified";
    counts.set(key, (counts.get(key) ?? 0) + 1);
    total += 1;
  }
  if (total === 0) return [];

  const slices: ClassificationSlice[] = [];
  for (const label of LABEL_ORDER) {
    const count = counts.get(label) ?? 0;
    if (count === 0) continue;
    slices.push({ key: label, label: LABEL_TEXT[label], count, fraction: count / total, color: LABEL_COLOR[label] });
  }
  const unclassified = counts.get("unclassified") ?? 0;
  if (unclassified > 0) {
    slices.push({
      key: "unclassified",
      label: "Not enough data yet",
      count: unclassified,
      fraction: unclassified / total,
      color: UNCLASSIFIED_COLOR,
    });
  }
  return slices;
}
