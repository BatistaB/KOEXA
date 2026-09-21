import type { Gene } from "../../data/types";
import type { GeneRanking } from "./rankingTypes";
import { GeneRankingChart } from "./GeneRankingChart";
import "./GeneRankingOverview.css";

const TOP_N = 40;

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
  const shown = rankings.slice(0, TOP_N);
  const isCapped = rankings.length > TOP_N;

  return (
    <div className="ranking-overview">
      <div className="ranking-overview__title">Genes by total expression</div>
      <p className="ranking-overview__subtitle">
        {isCapped
          ? `Top ${TOP_N} of ${rankings.length.toLocaleString("en-US")} genes`
          : `All ${rankings.length.toLocaleString("en-US")} genes`}
        , from most to least expressed — summed TPM across samples, stacked
        by sample and colored by study. {filterSummary}
        {isCapped && " Search above to jump to any other gene directly."}
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
