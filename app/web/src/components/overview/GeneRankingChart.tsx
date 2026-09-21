import { useMemo, useRef, useState } from "react";
import type { Gene } from "../../data/types";
import type { GeneRanking, RankingSegment } from "./rankingTypes";
import { niceLinearTicks } from "../../lib/chartScale";
import { rectPath, roundedTopBarPath } from "../../lib/barPath";
import { formatTpm } from "../../lib/format";
import { isSymbolicLabel, primaryGeneLabel, truncateLabel } from "../../lib/geneDisplay";
import { DatasetLink } from "../common/DatasetLink";
import "./GeneRankingChart.css";

interface GeneRankingChartProps {
  rankings: GeneRanking[];
  datasets: [string, string][];
  datasetColor: (bioproject: string) => string;
  onSelectGene: (gene: Gene) => void;
  onSelectDataset: (bioproject: string) => void;
}

const VB_W = 900;
const VB_H = 380;
const MARGIN = { top: 24, right: 20, bottom: 70, left: 60 };
const INNER_W = VB_W - MARGIN.left - MARGIN.right;
const INNER_H = VB_H - MARGIN.top - MARGIN.bottom;
const SEGMENT_GAP = 1;

interface HoverState {
  segment: RankingSegment;
  gene: Gene;
  total: number;
  x: number;
  y: number;
}

export function GeneRankingChart({
  rankings,
  datasets,
  datasetColor,
  onSelectGene,
  onSelectDataset,
}: GeneRankingChartProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [hover, setHover] = useState<HoverState | null>(null);
  const [hoveredGeneId, setHoveredGeneId] = useState<string | null>(null);

  const yMax = Math.max(1, ...rankings.map((r) => r.total)) * 1.12;
  const yScale = (value: number) => INNER_H - (value / yMax) * INNER_H;
  const ticks = useMemo(() => niceLinearTicks(yMax), [yMax]);

  const bandWidth = INNER_W / Math.max(1, rankings.length);
  const barWidth = Math.min(44, bandWidth * 0.5);

  const showTooltip = (segment: RankingSegment, gene: Gene, total: number, target: Element) => {
    const containerRect = containerRef.current?.getBoundingClientRect();
    const targetRect = target.getBoundingClientRect();
    if (!containerRect) return;
    setHover({
      segment,
      gene,
      total,
      x: targetRect.left + targetRect.width / 2 - containerRect.left,
      y: targetRect.top - containerRect.top,
    });
    setHoveredGeneId(gene.canonical_gene_id);
  };

  const clearTooltip = () => {
    setHover(null);
    setHoveredGeneId(null);
  };

  return (
    <div>
      <div className="ranking-chart__controls">
        <div className="ranking-chart__legend">
          {datasets.map(([bioproject, title]) => (
            <span className="ranking-chart__legend-item" key={bioproject} title={title}>
              <span className="ranking-chart__legend-dot" style={{ background: datasetColor(bioproject) }} />
              <DatasetLink bioproject={bioproject} onSelect={onSelectDataset} />
            </span>
          ))}
        </div>
        <span className="ranking-chart__hint">Click a bar to see the gene in detail</span>
      </div>

      <div className="ranking-chart__canvas" ref={containerRef}>
        <svg
          className="ranking-chart__svg"
          viewBox={`0 0 ${VB_W} ${VB_H}`}
          preserveAspectRatio="xMidYMid meet"
          role="img"
          aria-label="Genes ranked from most to least expressed, TPM summed per sample, stacked by sample and colored by study"
        >
          <g transform={`translate(${MARGIN.left},${MARGIN.top})`}>
            {ticks.map((t) => (
              <g key={t}>
                <line x1={0} x2={INNER_W} y1={yScale(t)} y2={yScale(t)} stroke="var(--chart-gridline)" strokeWidth={1} />
                <text x={-8} y={yScale(t)} textAnchor="end" dominantBaseline="middle" className="ranking-chart__tick-label">
                  {t.toLocaleString("en-US")}
                </text>
              </g>
            ))}

            <text
              className="ranking-chart__axis-label"
              transform={`translate(${-MARGIN.left + 16}, ${INNER_H / 2}) rotate(-90)`}
              textAnchor="middle"
            >
              TPM total (sum across samples)
            </text>

            <line x1={0} x2={INNER_W} y1={INNER_H} y2={INNER_H} stroke="var(--chart-axis)" strokeWidth={1} />

            {rankings.map((ranking, gi) => {
              const centerX = gi * bandWidth + bandWidth / 2;
              const barX = centerX - barWidth / 2;
              const isDimmed = hoveredGeneId !== null && hoveredGeneId !== ranking.gene.canonical_gene_id;
              let cumulative = 0;

              return (
                <g
                  key={ranking.gene.canonical_gene_id}
                  className="ranking-chart__bar-group"
                  style={{ opacity: isDimmed ? 0.45 : 1 }}
                  onClick={() => onSelectGene(ranking.gene)}
                >
                  {ranking.segments.map((segment, si) => {
                    const before = cumulative;
                    cumulative += segment.tpm;
                    const isLast = si === ranking.segments.length - 1;
                    const yTop = yScale(cumulative);
                    const yBottom = yScale(before);
                    let height = yBottom - yTop;
                    let top = yTop;
                    if (height > SEGMENT_GAP * 3) {
                      top += SEGMENT_GAP / 2;
                      height -= SEGMENT_GAP;
                    }
                    const path = isLast
                      ? roundedTopBarPath(barX, top, barWidth, height, 4)
                      : rectPath(barX, top, barWidth, height);
                    return (
                      <path
                        key={segment.sample.sample_id}
                        className="ranking-chart__segment"
                        d={path}
                        fill={datasetColor(segment.bioproject)}
                        onMouseMove={(e) => showTooltip(segment, ranking.gene, ranking.total, e.currentTarget)}
                        onMouseLeave={clearTooltip}
                        tabIndex={0}
                        role="button"
                        aria-label={`${primaryGeneLabel(ranking.gene)}, sample ${segment.sample.sample_id}, ${formatTpm(segment.tpm)} TPM`}
                        onFocus={(e) => showTooltip(segment, ranking.gene, ranking.total, e.currentTarget)}
                        onBlur={clearTooltip}
                        onKeyDown={(e) => {
                          if (e.key === "Enter" || e.key === " ") {
                            e.preventDefault();
                            onSelectGene(ranking.gene);
                          }
                        }}
                      />
                    );
                  })}

                  {gi === 0 && (
                    <text x={centerX} y={yScale(ranking.total) - 8} textAnchor="middle" className="ranking-chart__total-label">
                      {formatTpm(ranking.total)} TPM
                    </text>
                  )}

                  <text
                    x={centerX}
                    y={INNER_H + 14}
                    textAnchor="end"
                    transform={`rotate(-50, ${centerX}, ${INNER_H + 14})`}
                    className={
                      isSymbolicLabel(ranking.gene)
                        ? "ranking-chart__gene-label"
                        : "ranking-chart__gene-label ranking-chart__gene-label--plain"
                    }
                  >
                    {truncateLabel(primaryGeneLabel(ranking.gene))}
                  </text>
                </g>
              );
            })}
          </g>
        </svg>

        {hover && (
          <div className="ranking-chart__tooltip" style={{ left: hover.x, top: hover.y - 10 }}>
            <div className="ranking-chart__tooltip-gene">{primaryGeneLabel(hover.gene)}</div>
            <div className="ranking-chart__tooltip-value">{formatTpm(hover.segment.tpm)} TPM</div>
            <div className="ranking-chart__tooltip-row mono">{hover.segment.sample.sample_id}</div>
            <div className="ranking-chart__tooltip-row">{hover.segment.bioproject}</div>
            {hover.segment.condition && (
              <div className="ranking-chart__tooltip-row">{hover.segment.condition.condition_label}</div>
            )}
            <div className="ranking-chart__tooltip-total">gene total: {formatTpm(hover.total)} TPM</div>
          </div>
        )}
      </div>
    </div>
  );
}
