/**
 * Deterministic filler TPM for genes outside the 9 hand-curated "hero"
 * genes in fixtures.ts. Needed because the real RIB40 gene catalog
 * (12,090 genes, exported by scripts/export_gene_catalog.py) has no real
 * expression yet -- Milestone 5/6 haven't produced full-genome
 * quantification. This exists purely to stress-test the UI at real
 * genome scale (ranking chart, search, table rendering) with a plausible
 * TPM distribution, not to claim any biological signal.
 *
 * No condition-dependent pattern here (unlike the hero genes' curated
 * BASELINE_TPM table) -- each gene gets one fixed baseline (log-spread,
 * skewed toward low expression like real RNA-seq) plus small per-sample
 * technical noise. A fast string hash, not Math.random, so results are
 * stable across renders/reloads without storing 12,090 x 26 values.
 */
import type { Sample } from "../data/types";

function hash32(str: string): number {
  let h = 2166136261;
  for (let i = 0; i < str.length; i++) {
    h ^= str.charCodeAt(i);
    h = Math.imul(h, 16777619);
  }
  return h >>> 0;
}

function unitFromHash(h: number): number {
  // xorshift finalizer to spread hash bits before taking it as [0,1)
  let x = h ^ 0x9e3779b9;
  x ^= x << 13;
  x ^= x >>> 17;
  x ^= x << 5;
  return (x >>> 0) / 4294967296;
}

export function syntheticExpression(
  geneId: string,
  sample: Sample,
): { tpm: number; estimatedCounts: number } {
  const baselineUnit = unitFromHash(hash32(geneId));
  // Skew toward low expression (most genes lowly expressed, long tail of
  // highly expressed ones) by compressing the unit interval before
  // mapping to a log10 exponent in roughly [-1, 3.3].
  const exponent = -1 + Math.pow(baselineUnit, 2.1) * 4.3;
  const baseline = Math.pow(10, exponent);

  const noiseUnit = unitFromHash(hash32(`${geneId}|${sample.sample_id}`));
  const noiseFactor = Math.exp((noiseUnit - 0.5) * 0.9);
  const dropoutPenalty = sample.qc_status === "warning" ? 0.6 : 1;

  // Lowly-expressed genes have a real chance of going undetected (TPM=0)
  // in any given sample, same as real RNA-seq -- without this every one
  // of ~12k genes would show as "detected" in every sample, which isn't
  // a realistic distribution to stress-test the UI against.
  const detectionRoll = unitFromHash(hash32(`${geneId}|${sample.sample_id}|detect`));
  const detectionProbability = Math.min(1, baseline * 2);
  if (detectionRoll > detectionProbability) {
    return { tpm: 0, estimatedCounts: 0 };
  }

  const tpm = Math.max(0, baseline * noiseFactor * dropoutPenalty);
  const estimatedCounts = Math.round((tpm / 1_000_000) * sample.read_count * 0.85);

  return { tpm: Math.round(tpm * 100) / 100, estimatedCounts };
}
