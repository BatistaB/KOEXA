import type { Gene } from "../../data/types";

/** One study's summed contribution to a gene's total — the home chart
 * deliberately stops at study level; per-sample detail lives in the gene
 * view, reached by clicking a study segment. */
export interface RankingSegment {
  bioproject: string;
  tpm: number;
  sampleCount: number;
}

export interface GeneRanking {
  gene: Gene;
  total: number;
  segments: RankingSegment[];
}
