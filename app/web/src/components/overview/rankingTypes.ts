import type { Condition, Gene, Sample } from "../../data/types";

export interface RankingSegment {
  sample: Sample;
  condition: Condition | undefined;
  bioproject: string;
  tpm: number;
}

export interface GeneRanking {
  gene: Gene;
  total: number;
  segments: RankingSegment[];
}
