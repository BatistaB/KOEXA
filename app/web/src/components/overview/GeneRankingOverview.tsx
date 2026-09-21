import { useMemo, useState } from "react";
import type { Gene } from "../../data/types";
import type { GeneRanking } from "./rankingTypes";
import { DENSE_THRESHOLD, GeneRankingChart } from "./GeneRankingChart";
import "./GeneRankingOverview.css";

const STEP_VALUES = [10, 25, 40, 100, 250, 500, 1000, 2500, 5000];
const DEFAULT_COUNT = 40;

interface GeneRankingOverviewProps {
  rankings: GeneRanking[];
  datasets: [string, string][];
  datasetColor: (bioproject: string) => string;
  onSelectGene: (gene: Gene) => void;
  onSelectDataset: (bioproject: string) => void;
  filterSummary: string;
}

export function GeneRankingOverview({
  rankings,
  datasets,
  datasetColor,
  onSelectGene,
  onSelectDataset,
  filterSummary,
}: GeneRankingOverviewProps) {
  const [selectedCount, setSelectedCount] = useState(DEFAULT_COUNT);

  const steps = useMemo(() => {
    const capped = STEP_VALUES.filter((n) => n < rankings.length);
    return [...capped, rankings.length];
  }, [rankings.length]);

  const sliderIndex = Math.max(
    0,
    steps.findIndex((s) => s >= selectedCount),
  );
  const shownCount = steps[sliderIndex] ?? rankings.length;
  const isAll = shownCount >= rankings.length;
  const shown = rankings.slice(0, shownCount);
  const isDense = shownCount > DENSE_THRESHOLD;

  return (
    <div className="ranking-overview">
      <div className="ranking-overview__title">Genes by total expression</div>

      <div className="ranking-overview__zoom">
        <span className="ranking-overview__zoom-label">Genes shown</span>
        <input
          type="range"
          className="ranking-overview__zoom-slider"
          min={0}
          max={Math.max(0, steps.length - 1)}
          step={1}
          value={sliderIndex}
          onChange={(e) => setSelectedCount(steps[Number(e.target.value)] ?? DEFAULT_COUNT)}
          aria-label="Number of genes to show in the ranking chart"
        />
        <span className="ranking-overview__zoom-value">
          {isAll ? `All ${rankings.length.toLocaleString("en-US")}` : shownCount.toLocaleString("en-US")}
        </span>
      </div>

      <p className="ranking-overview__subtitle">
        {isAll ? "Every gene" : `Top ${shownCount.toLocaleString("en-US")} of ${rankings.length.toLocaleString("en-US")} genes`}
        , from most to least expressed — summed TPM across samples, colored
        by study. {filterSummary}
        {isDense
          ? " Individual labels are hidden at this density — hover or click a position to inspect the gene there."
          : " Search above to jump to any other gene directly."}
      </p>

      {shown.length === 0 ? (
        <div className="ranking-overview__empty">
          No samples match the current filter.
        </div>
      ) : (
        <GeneRankingChart
          rankings={shown}
          datasets={datasets}
          datasetColor={datasetColor}
          onSelectGene={onSelectGene}
          onSelectDataset={onSelectDataset}
        />
      )}
    </div>
  );
}
