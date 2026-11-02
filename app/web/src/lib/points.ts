import type {
  Condition,
  Dataset,
  Gene,
  Sample,
} from "../data/types";
import type { ChartPoint } from "../components/gene/chartTypes";
import type { GeneRanking } from "../components/overview/rankingTypes";
import type { ExpressionMatrix } from "../data/expressionMatrix";

export function buildChartPoints(
  gene: Gene,
  samples: Sample[],
  conditions: Condition[],
  datasets: Dataset[],
  expression: ExpressionMatrix,
  strainFilter: string,
  conditionFilter: string = "all",
): ChartPoint[] {
  const conditionById = new Map(conditions.map((c) => [c.condition_id, c]));
  const datasetByBioproject = new Map(datasets.map((d) => [d.bioproject, d]));
  const points: ChartPoint[] = [];
  for (const sample of samples) {
    if (strainFilter !== "all" && sample.strain !== strainFilter) continue;
    if (conditionFilter !== "all" && sample.condition_id !== conditionFilter) continue;
    const condition = conditionById.get(sample.condition_id);
    if (!condition) continue;
    const tpm = expression.tpmAt(gene.canonical_gene_id, sample.sample_id);
    if (tpm <= 0) continue;
    const estimatedCounts = expression.countsAt(gene.canonical_gene_id, sample.sample_id);
    points.push({
      sample,
      condition,
      dataset: datasetByBioproject.get(sample.bioproject),
      tpm,
      estimatedCounts,
    });
  }
  return points;
}

/**
 * Ranks every gene by summed TPM across the filtered sample set — "which
 * genes dominate total expression in this slice of the atlas," not a
 * per-sample comparison. Each bar is stacked by study (one segment per
 * BioProject, TPM summed over that study's samples), ordered to match the
 * shared legend; per-sample detail is the gene view's job, not this chart's.
 */
export function buildGeneRankings(
  genes: Gene[],
  samples: Sample[],
  datasets: Dataset[],
  expression: ExpressionMatrix,
  strainFilter: string,
  conditionFilter: string = "all",
): GeneRanking[] {
  const datasetOrder = new Map(datasets.map((d, i) => [d.bioproject, i]));
  const eligible = samples.filter((s) => {
    if (strainFilter !== "all" && s.strain !== strainFilter) return false;
    if (conditionFilter !== "all" && s.condition_id !== conditionFilter) return false;
    return true;
  });
  // Resolve the eligible columns once, then each gene is a straight scan of its matrix row.
  const cols: { col: number; bioproject: string }[] = [];
  for (const s of eligible) {
    const col = expression.colOf(s.sample_id);
    if (col !== undefined) cols.push({ col, bioproject: s.bioproject });
  }
  const bioprojects = Array.from(new Set(cols.map((c) => c.bioproject)));
  const slot = new Map(bioprojects.map((b, i) => [b, i]));
  const colSlot = cols.map((c) => slot.get(c.bioproject)!);
  const order = bioprojects
    .map((b, i) => [b, i] as const)
    .sort((a, b) => (datasetOrder.get(a[0]) ?? 0) - (datasetOrder.get(b[0]) ?? 0));
  const { tpm, nSamples } = expression;

  const rankings: GeneRanking[] = genes.map((gene) => {
    const row = expression.rowOf(gene.canonical_gene_id);
    const sums = new Float64Array(bioprojects.length);
    const counts = new Uint32Array(bioprojects.length);
    let total = 0;
    if (row !== undefined) {
      const base = row * nSamples;
      for (let i = 0; i < cols.length; i++) {
        const v = tpm[base + cols[i].col];
        if (v <= 0) continue;
        total += v;
        sums[colSlot[i]] += v;
        counts[colSlot[i]] += 1;
      }
    }
    const segments = [];
    for (const [bioproject, i] of order) {
      if (counts[i] > 0) segments.push({ bioproject, tpm: sums[i], sampleCount: counts[i] });
    }
    return { gene, total, segments };
  });

  return rankings.sort((a, b) => b.total - a.total);
}

export function median(values: number[]): number {
  if (values.length === 0) return 0;
  const sorted = [...values].sort((a, b) => a - b);
  const mid = Math.floor(sorted.length / 2);
  return sorted.length % 2 === 0 ? (sorted[mid - 1] + sorted[mid]) / 2 : sorted[mid];
}

export function datasetColorAssignment(datasets: Dataset[]): Map<string, string> {
  const colors = ["--series-1", "--series-2", "--series-3", "--series-4", "--series-5", "--series-6"];
  const map = new Map<string, string>();
  datasets.forEach((d, i) => {
    map.set(d.bioproject, `var(${colors[i % colors.length]})`);
  });
  return map;
}
