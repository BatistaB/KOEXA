import type { Gene } from "../../data/types";
import type { ChartPoint } from "./chartTypes";
import type { ChartScale } from "./ExpressionChart";
import { GeneHeader } from "./GeneHeader";
import { ExpressionChart } from "./ExpressionChart";
import { SampleTable } from "./SampleTable";
import { Skeleton } from "../common/Skeleton";
import "./GeneWorkspace.css";

interface GeneWorkspaceProps {
  gene: Gene;
  points: ChartPoint[];
  datasetColor: (bioproject: string) => string;
  scale: ChartScale;
  onScaleChange: (scale: ChartScale) => void;
  selectedSampleId: string | null;
  hoveredSampleId: string | null;
  onHoverSample: (id: string | null) => void;
  onSelectSample: (id: string) => void;
  onSelectDataset: (bioproject: string) => void;
  studyScope: string | null;
  onClearStudyScope: () => void;
  loading: boolean;
  onBack: () => void;
}

export function GeneWorkspace({
  gene,
  points,
  datasetColor,
  scale,
  onScaleChange,
  selectedSampleId,
  hoveredSampleId,
  onHoverSample,
  onSelectSample,
  onSelectDataset,
  studyScope,
  onClearStudyScope,
  loading,
  onBack,
}: GeneWorkspaceProps) {
  return (
    <div className="gene-workspace">
      <button type="button" className="gene-workspace__back" onClick={onBack}>
        ← All genes
      </button>
      <GeneHeader gene={gene} />
      {studyScope && (
        <div className="gene-workspace__scope" role="status">
          <span className="gene-workspace__scope-dot" style={{ background: datasetColor(studyScope) }} />
          <span>
            Showing sample-level expression for study <strong className="mono">{studyScope}</strong> only
          </span>
          <button type="button" className="gene-workspace__scope-clear" onClick={onClearStudyScope}>
            Show all studies
          </button>
        </div>
      )}
      {loading ? (
        <div className="gene-workspace__skeleton-chart">
          <Skeleton height={320} />
        </div>
      ) : (
        <>
          <ExpressionChart
            points={points}
            datasetColor={datasetColor}
            scale={scale}
            onScaleChange={onScaleChange}
            selectedSampleId={selectedSampleId}
            hoveredSampleId={hoveredSampleId}
            onHoverSample={onHoverSample}
            onSelectSample={onSelectSample}
            onSelectDataset={onSelectDataset}
          />
          <SampleTable
            geneSymbol={gene.gene_symbol ?? gene.canonical_gene_id}
            points={points}
            selectedSampleId={selectedSampleId}
            hoveredSampleId={hoveredSampleId}
            onHoverSample={onHoverSample}
            onSelectSample={onSelectSample}
            onSelectDataset={onSelectDataset}
          />
        </>
      )}
    </div>
  );
}
