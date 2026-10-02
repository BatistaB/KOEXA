import type {
  Condition,
  Dataset,
  Gene,
  GeneExpressionRow,
  Sample,
} from "../data/types";
import type { ChartPoint } from "../components/gene/chartTypes";
import type { GeneRanking } from "../components/overview/rankingTypes";
import { syntheticExpression } from "./syntheticExpression";

/**
 * Curated (hero-gene) TPM lives in a small hand-authored array; every
 * other gene in the real 12k-gene catalog falls back to deterministic
 * synthetic filler (lib/syntheticExpression.ts) computed on demand rather
 * than precomputed for every gene x sample pair, which would be ~314k
 * rows for no benefit.
 */
function makeExpressionGetter(curated: GeneExpressionRow[]) {
  const curatedByKey = new Map(curated.map((e) => [`${e.sample_id}|${e.canonical_gene_id}`, e]));
  return (geneId: string, sample: Sample): { tpm: number; estimatedCounts: number } => {
    const row = curatedByKey.get(`${sample.sample_id}|${geneId}`);
    if (row) return { tpm: row.TPM, estimatedCounts: row.estimated_counts };
    return syntheticExpression(geneId, sample);
  };
}

export function buildChartPoints(
  gene: Gene,
  samples: Sample[],
  conditions: Condition[],
  datasets: Dataset[],
  expression: GeneExpressionRow[],
  strainFilter: string,
  conditionFilter: string = "all",
): ChartPoint[] {
  const conditionById = new Map(conditions.map((c) => [c.condition_id, c]));
  const datasetByBioproject = new Map(datasets.map((d) => [d.bioproject, d]));
  const getExpression = makeExpressionGetter(expression);

  const points: ChartPoint[] = [];
  for (const sample of samples) {
    if (strainFilter !== "all" && sample.strain !== strainFilter) continue;
    if (conditionFilter !== "all" && sample.condition_id !== conditionFilter) continue;
    const condition = conditionById.get(sample.condition_id);
    if (!condition) continue;
    const { tpm, estimatedCounts } = getExpression(gene.canonical_gene_id, sample);
    if (tpm <= 0) continue;
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
  expression: GeneExpressionRow[],
  strainFilter: string,
  conditionFilter: string = "all",
): GeneRanking[] {
  const datasetOrder = new Map(datasets.map((d, i) => [d.bioproject, i]));
  const eligibleSamples = samples.filter((s) => {
    if (strainFilter !== "all" && s.strain !== strainFilter) return false;
    if (conditionFilter !== "all" && s.condition_id !== conditionFilter) return false;
    return true;
  });
  const getExpression = makeExpressionGetter(expression);

  const rankings: GeneRanking[] = genes.map((gene) => {
    const byStudy = new Map<string, { tpm: number; sampleCount: number }>();
    let total = 0;
    for (const sample of eligibleSamples) {
      const { tpm } = getExpression(gene.canonical_gene_id, sample);
      if (tpm <= 0) continue;
      total += tpm;
      const acc = byStudy.get(sample.bioproject) ?? { tpm: 0, sampleCount: 0 };
      acc.tpm += tpm;
      acc.sampleCount += 1;
      byStudy.set(sample.bioproject, acc);
    }
    const segments = Array.from(byStudy, ([bioproject, v]) => ({ bioproject, ...v })).sort(
      (a, b) => (datasetOrder.get(a.bioproject) ?? 0) - (datasetOrder.get(b.bioproject) ?? 0),
    );
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
