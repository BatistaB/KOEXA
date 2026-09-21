import type { Condition, Dataset, Sample } from "../../data/types";

export interface ChartPoint {
  sample: Sample;
  condition: Condition;
  dataset: Dataset | undefined;
  tpm: number;
  estimatedCounts: number;
}
