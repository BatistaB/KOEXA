import type {
  ChromosomeExpression,
  Condition,
  Dataset,
  ExpressionRank,
  ExpressionRankRow,
  ExpressionRankSummary,
  GeneClassification,
  GeneExpressionRow,
  Sample,
  SampleQcMetrics,
} from "./types";

/**
 * Loads the real, DuckDB-backed atlas snapshot (public/data/{datasets,
 * conditions,samples,sample_qc,expression,classification}.json) fetched at
 * runtime, produced by `atlas app export-web` (src/aoryzae_atlas/webexport/
 * build.py) -- the standardized bridge that regenerates these every time
 * `atlas refresh` runs. Only samples that are QUANTIFIED and
 * condition-curated are included; see webexport/build.py's
 * CURATED_QUANTIFIED_FILTER.
 *
 * datasets/conditions/samples/sample_qc.json are plain object arrays
 * (small at pilot scale). expression.json and classification.json are
 * compact tuple rows (large: ~495k expression rows at the current 41-
 * sample pilot) -- same convention as data/realGenes.ts's genes.json.
 */

export interface RealAtlasData {
  datasets: Dataset[];
  conditions: Condition[];
  samples: Sample[];
  sampleQc: SampleQcMetrics[];
  expression: GeneExpressionRow[];
  classification: Map<string, GeneClassification>;
  /** null until `atlas rank genes` has run and the web export has been refreshed. */
  expressionRank: ExpressionRank | null;
  chromosomeExpression: ChromosomeExpression | null;
}

interface ExpressionRow {
  columns: string[];
  rows: [string, string, number | null, number | null][];
}

interface ClassificationRow {
  columns: string[];
  rows: [
    string,
    number,
    number,
    number,
    number | null,
    number | null,
    number | null,
    number | null,
    number | null,
    string | null,
    string,
  ][];
}

interface ExpressionRankPayload {
  columns: string[];
  rows: [
    string, string, number, number, number, number, number, number, number, number, number, number,
    number, number, number, number | null, string,
  ][];
  summary: ExpressionRankSummary | null;
}

interface ChromosomeExpressionPayload {
  bin_size_bp: number;
  bin_columns: string[];
  chromosomes: {
    chromosome: string;
    length: number;
    bins: [number, number, number, number, number | null, number | null][];
  }[];
}

function parseExpressionRank(payload: ExpressionRankPayload): ExpressionRank {
  const rows: ExpressionRankRow[] = payload.rows.map((r) => ({
    canonical_gene_id: r[0],
    expression_class: r[1] as ExpressionRankRow["expression_class"],
    level_score: r[2],
    stability_score: r[3],
    specificity_score: r[4],
    prevalence_score: r[5],
    global_rank: r[6],
    rank_most_expressed: r[7],
    rank_most_stable: r[8],
    rank_most_variable: r[9],
    rank_most_specific: r[10],
    rank_rarest: r[11],
    median_TPM: r[12],
    prevalence_TPM_1: r[13],
    MAD_logTPM: r[14],
    Tau: r[15],
    quality_flags: r[16],
  }));
  return { summary: payload.summary, rows, byGene: new Map(rows.map((row) => [row.canonical_gene_id, row])) };
}

function parseChromosomeExpression(payload: ChromosomeExpressionPayload): ChromosomeExpression {
  return {
    binSizeBp: payload.bin_size_bp,
    chromosomes: payload.chromosomes.map((track) => ({
      chromosome: track.chromosome,
      length: track.length,
      bins: track.bins.map(([start, end, nGenes, nDetectedGenes, meanTpm, log10MeanTpm]) => ({
        start,
        end,
        nGenes,
        nDetectedGenes,
        meanTpm,
        log10MeanTpm,
      })),
    })),
  };
}

async function fetchJson<T>(path: string): Promise<T> {
  const res = await fetch(path);
  if (!res.ok) {
    throw new Error(`Failed to load ${path}: ${res.status} ${res.statusText}`);
  }
  return (await res.json()) as T;
}

function parseExpression(payload: ExpressionRow): GeneExpressionRow[] {
  return payload.rows.map(([sample_id, canonical_gene_id, TPM, estimated_counts]) => ({
    sample_id,
    canonical_gene_id,
    TPM: TPM ?? 0,
    estimated_counts: estimated_counts ?? 0,
  }));
}

function parseClassification(payload: ClassificationRow): Map<string, GeneClassification> {
  const map = new Map<string, GeneClassification>();
  for (const row of payload.rows) {
    const [
      canonical_gene_id,
      median_TPM,
      n_detected_conditions,
      n_conditions,
      Tau_log1p,
      Tau_raw,
      prevalence_TPM_1,
      robust_CV,
      cluster_base,
      biological_label,
      classification_confidence,
    ] = row;
    map.set(canonical_gene_id, {
      canonical_gene_id,
      median_TPM,
      n_detected_conditions,
      n_conditions,
      Tau_log1p,
      Tau_raw,
      prevalence_TPM_1,
      robust_CV,
      cluster_base,
      biological_label: biological_label as GeneClassification["biological_label"],
      classification_confidence: classification_confidence as GeneClassification["classification_confidence"],
    });
  }
  return map;
}

export async function loadRealAtlas(): Promise<RealAtlasData> {
  const [datasets, conditions, samples, sampleQc, expressionPayload, classificationPayload, chromosomeExpressionPayload, expressionRankPayload] =
    await Promise.all([
      fetchJson<Dataset[]>("/data/datasets.json"),
      fetchJson<Condition[]>("/data/conditions.json"),
      fetchJson<Sample[]>("/data/samples.json"),
      fetchJson<SampleQcMetrics[]>("/data/sample_qc.json"),
      fetchJson<ExpressionRow>("/data/expression.json"),
      fetchJson<ClassificationRow | null>("/data/classification.json").catch(() => null),
      fetchJson<ChromosomeExpressionPayload | null>("/data/chromosome_expression.json").catch(() => null),
      fetchJson<ExpressionRankPayload | null>("/data/expression_rank.json").catch(() => null),
    ]);

  return {
    datasets,
    conditions,
    samples,
    sampleQc,
    expression: parseExpression(expressionPayload),
    classification: classificationPayload ? parseClassification(classificationPayload) : new Map(),
    expressionRank: expressionRankPayload ? parseExpressionRank(expressionRankPayload) : null,
    chromosomeExpression: chromosomeExpressionPayload ? parseChromosomeExpression(chromosomeExpressionPayload) : null,
  };
}
