import type {
  Condition,
  Dataset,
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
  const [datasets, conditions, samples, sampleQc, expressionPayload, classificationPayload] = await Promise.all([
    fetchJson<Dataset[]>("/data/datasets.json"),
    fetchJson<Condition[]>("/data/conditions.json"),
    fetchJson<Sample[]>("/data/samples.json"),
    fetchJson<SampleQcMetrics[]>("/data/sample_qc.json"),
    fetchJson<ExpressionRow>("/data/expression.json"),
    fetchJson<ClassificationRow | null>("/data/classification.json").catch(() => null),
  ]);

  return {
    datasets,
    conditions,
    samples,
    sampleQc,
    expression: parseExpression(expressionPayload),
    classification: classificationPayload ? parseClassification(classificationPayload) : new Map(),
  };
}
