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
  /** `bioproject` is set when a specific study segment was clicked, so the
   * gene view can open scoped to that study's samples. */
  onSelectGene: (gene: Gene, bioproject?: string) => void;
  onSelectDataset: (bioproject: string) => void;
}

const VB_W = 900;
const VB_H = 380;
const MARGIN = { top: 24, right: 20, bottom: 70, left: 60 };
const INNER_W = VB_W - MARGIN.left - MARGIN.right;
const INNER_H = VB_H - MARGIN.top - MARGIN.bottom;
const SEGMENT_GAP = 1;

/** Past this many bars, per-gene text labels and per-sample segments stop
 * being legible or renderable at reasonable cost — switch to an
 * aggregated "skyline" with crosshair hover instead of per-bar hit
 * targets. Bars are stacked by study in both modes. Exported so the overview can word its hint text accordingly. */
export const DENSE_THRESHOLD = 60;

interface LabeledHoverState {
  segment: RankingSegment;
  gene: Gene;
  total: number;
  x: number;
  y: number;
}

interface DenseHoverState {
  index: number;
  screenX: number;
  screenY: number;
}

export function GeneRankingChart({
  rankings,
  datasets,
  datasetColor,
  onSelectGene,
  onSelectDataset,
}: GeneRankingChartProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const overlayRef = useRef<SVGRectElement>(null);
  const [labeledHover, setLabeledHover] = useState<LabeledHoverState | null>(null);
  const [hoveredGeneId, setHoveredGeneId] = useState<string | null>(null);
  const [denseHover, setDenseHover] = useState<DenseHoverState | null>(null);

  const dense = rankings.length > DENSE_THRESHOLD;
  const yMax = Math.max(1, ...rankings.map((r) => r.total)) * 1.12;
  const yScale = (value: number) => INNER_H - (value / yMax) * INNER_H;
  const ticks = useMemo(() => niceLinearTicks(yMax), [yMax]);

  const bandWidth = INNER_W / Math.max(1, rankings.length);
  const barWidth = dense ? Math.max(bandWidth * 0.86, 0.35) : Math.min(44, bandWidth * 0.5);

  const showLabeledTooltip = (segment: RankingSegment, gene: Gene, total: number, target: Element) => {
    const containerRect = containerRef.current?.getBoundingClientRect();
    const targetRect = target.getBoundingClientRect();
    if (!containerRect) return;
    setLabeledHover({
      segment,
      gene,
      total,
      x: targetRect.left + targetRect.width / 2 - containerRect.left,
      y: targetRect.top - containerRect.top,
    });
    setHoveredGeneId(gene.canonical_gene_id);
  };

  const clearLabeledTooltip = () => {
    setLabeledHover(null);
    setHoveredGeneId(null);
  };

  // Dense mode: one <path> per dataset color spanning every bar, instead of
  // one element per gene x sample segment — keeps the DOM at O(datasets)
  // regardless of whether we're showing 100 genes or all 12k+.
  const densePaths = useMemo(() => {
    if (!dense) return null;
    const byDataset = new Map<string, string[]>();
    rankings.forEach((ranking, gi) => {
      const centerX = gi * bandWidth + bandWidth / 2;
      const barX = centerX - barWidth / 2;
      let cumulative = 0;
      for (const { bioproject, tpm } of ranking.segments) {
        const before = cumulative;
        cumulative += tpm;
        const yTop = INNER_H - (cumulative / yMax) * INNER_H;
        const yBottom = INNER_H - (before / yMax) * INNER_H;
        const height = yBottom - yTop;
        if (height <= 0) continue;
        const list = byDataset.get(bioproject) ?? [];
        list.push(rectPath(barX, yTop, barWidth, height));
        byDataset.set(bioproject, list);
      }
    });
    return byDataset;
  }, [dense, rankings, bandWidth, barWidth, yMax]);

  const resolveDenseIndex = (clientX: number): number => {
    const overlayRect = overlayRef.current?.getBoundingClientRect();
    if (!overlayRect || overlayRect.width === 0) return 0;
    const scaleX = overlayRect.width / INNER_W;
    const localSvgX = (clientX - overlayRect.left) / scaleX;
    return Math.min(rankings.length - 1, Math.max(0, Math.floor(localSvgX / bandWidth)));
  };

  /** Which study's stack segment sits at this vertical position of the
   * clicked bar, or undefined if the click landed above the bar. */
  const resolveStudyAtY = (ranking: GeneRanking, clientY: number): string | undefined => {
    const overlayRect = overlayRef.current?.getBoundingClientRect();
    if (!overlayRect || overlayRect.height === 0) return undefined;
    const svgY = ((clientY - overlayRect.top) / overlayRect.height) * INNER_H;
    const value = ((INNER_H - svgY) / INNER_H) * yMax;
    let cumulative = 0;
    for (const seg of ranking.segments) {
      cumulative += seg.tpm;
      if (value <= cumulative) return seg.bioproject;
    }
    return undefined;
  };

  const showDenseHoverAt = (index: number, clientX: number) => {
    const containerRect = containerRef.current?.getBoundingClientRect();
    const overlayRect = overlayRef.current?.getBoundingClientRect();
    if (!containerRect || !overlayRect) return;
    setDenseHover({
      index,
      screenX: clientX - containerRect.left,
      screenY: overlayRect.top - containerRect.top,
    });
  };

  const denseHoverRanking = denseHover ? rankings[denseHover.index] : null;

  const legend = (
    <div className="ranking-chart__legend">
      {datasets.map(([bioproject, title]) => (
        <span className="ranking-chart__legend-item" key={bioproject} title={title}>
          <span className="ranking-chart__legend-dot" style={{ background: datasetColor(bioproject) }} />
          <DatasetLink bioproject={bioproject} onSelect={onSelectDataset} />
        </span>
      ))}
    </div>
  );

  return (
    <div>
      <div className="ranking-chart__controls">
        {legend}
        <span className="ranking-chart__hint">
          {dense ? "Hover to inspect a gene — click a colored band to see that study sample by sample" : "Click a study segment to see that gene sample by sample"}
        </span>
      </div>

      <div className="ranking-chart__canvas" ref={containerRef}>
        <svg
          className="ranking-chart__svg"
          viewBox={`0 0 ${VB_W} ${VB_H}`}
          preserveAspectRatio="xMidYMid meet"
          role="img"
          aria-label={`${rankings.length.toLocaleString("en-US")} genes ranked from most to least expressed, TPM summed per study`}
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
              TPM total (sum across samples, stacked by study)
            </text>

            <line x1={0} x2={INNER_W} y1={INNER_H} y2={INNER_H} stroke="var(--chart-axis)" strokeWidth={1} />

            {dense
              ? densePaths &&
                Array.from(densePaths.entries()).map(([bioproject, segments]) => (
                  <path key={bioproject} d={segments.join(" ")} fill={datasetColor(bioproject)} />
                ))
              : rankings.map((ranking, gi) => {
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
                            key={segment.bioproject}
                            className="ranking-chart__segment"
                            d={path}
                            fill={datasetColor(segment.bioproject)}
                            onMouseMove={(e) => showLabeledTooltip(segment, ranking.gene, ranking.total, e.currentTarget)}
                            onMouseLeave={clearLabeledTooltip}
                            tabIndex={0}
                            role="button"
                            aria-label={`${primaryGeneLabel(ranking.gene)}, study ${segment.bioproject}, ${formatTpm(segment.tpm)} TPM summed over ${segment.sampleCount} samples — open sample by sample`}
                            onClick={(e) => {
                              e.stopPropagation();
                              onSelectGene(ranking.gene, segment.bioproject);
                            }}
                            onFocus={(e) => showLabeledTooltip(segment, ranking.gene, ranking.total, e.currentTarget)}
                            onBlur={clearLabeledTooltip}
                            onKeyDown={(e) => {
                              if (e.key === "Enter" || e.key === " ") {
                                e.preventDefault();
                                onSelectGene(ranking.gene, segment.bioproject);
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

            {dense && rankings.length > 0 && (
              <>
                {rankings[0] && (
                  <text x={bandWidth / 2} y={yScale(rankings[0].total) - 8} textAnchor="middle" className="ranking-chart__total-label">
                    {formatTpm(rankings[0].total)} TPM
                  </text>
                )}
                {[0, 0.25, 0.5, 0.75, 1].map((frac) => {
                  const idx = Math.round(frac * (rankings.length - 1));
                  const x = idx * bandWidth + bandWidth / 2;
                  return (
                    <text key={frac} x={x} y={INNER_H + 18} textAnchor="middle" className="ranking-chart__rank-label">
                      #{(idx + 1).toLocaleString("en-US")}
                    </text>
                  );
                })}
                {denseHover && (
                  <line
                    x1={denseHover.index * bandWidth + bandWidth / 2}
                    x2={denseHover.index * bandWidth + bandWidth / 2}
                    y1={0}
                    y2={INNER_H}
                    stroke="var(--text-muted)"
                    strokeWidth={1}
                    strokeDasharray="2,2"
                    pointerEvents="none"
                  />
                )}
                <rect
                  ref={overlayRef}
                  x={0}
                  y={0}
                  width={INNER_W}
                  height={INNER_H}
                  fill="transparent"
                  tabIndex={0}
                  role="slider"
                  aria-label="Explore ranked genes by position"
                  aria-valuemin={1}
                  aria-valuemax={rankings.length}
                  aria-valuenow={(denseHover?.index ?? 0) + 1}
                  aria-valuetext={denseHoverRanking ? primaryGeneLabel(denseHoverRanking.gene) : undefined}
                  onMouseMove={(e) => showDenseHoverAt(resolveDenseIndex(e.clientX), e.clientX)}
                  onMouseLeave={() => setDenseHover(null)}
                  onFocus={() => showDenseHoverAt(denseHover?.index ?? 0, containerRef.current?.getBoundingClientRect().left ?? 0)}
                  onBlur={() => setDenseHover(null)}
                  onClick={(e) => {
                    const idx = resolveDenseIndex(e.clientX);
                    const ranking = rankings[idx];
                    if (ranking) onSelectGene(ranking.gene, resolveStudyAtY(ranking, e.clientY));
                  }}
                  onKeyDown={(e) => {
                    const current = denseHover?.index ?? 0;
                    if (e.key === "ArrowRight") {
                      e.preventDefault();
                      const next = Math.min(rankings.length - 1, current + 1);
                      const overlayRect = overlayRef.current?.getBoundingClientRect();
                      if (overlayRect) showDenseHoverAt(next, overlayRect.left + (next + 0.5) * bandWidth * (overlayRect.width / INNER_W));
                    } else if (e.key === "ArrowLeft") {
                      e.preventDefault();
                      const prev = Math.max(0, current - 1);
                      const overlayRect = overlayRef.current?.getBoundingClientRect();
                      if (overlayRect) showDenseHoverAt(prev, overlayRect.left + (prev + 0.5) * bandWidth * (overlayRect.width / INNER_W));
                    } else if (e.key === "Enter" || e.key === " ") {
                      e.preventDefault();
                      const ranking = rankings[current];
                      if (ranking) onSelectGene(ranking.gene);
                    }
                  }}
                />
              </>
            )}
          </g>
        </svg>

        {!dense && labeledHover && (
          <div className="ranking-chart__tooltip" style={{ left: labeledHover.x, top: labeledHover.y - 10 }}>
            <div className="ranking-chart__tooltip-gene">{primaryGeneLabel(labeledHover.gene)}</div>
            <div className="ranking-chart__tooltip-value">{formatTpm(labeledHover.segment.tpm)} TPM</div>
            <div className="ranking-chart__tooltip-row mono">{labeledHover.segment.bioproject}</div>
            <div className="ranking-chart__tooltip-row">
              sum over {labeledHover.segment.sampleCount} sample{labeledHover.segment.sampleCount === 1 ? "" : "s"}
              {labeledHover.total > 0 ? ` · ${Math.round((labeledHover.segment.tpm / labeledHover.total) * 100)}% of total` : ""}
            </div>
            <div className="ranking-chart__tooltip-row">click to see samples</div>
            <div className="ranking-chart__tooltip-total">gene total: {formatTpm(labeledHover.total)} TPM</div>
          </div>
        )}

        {dense && denseHover && denseHoverRanking && (
          <div className="ranking-chart__tooltip" style={{ left: denseHover.screenX, top: denseHover.screenY - 10 }}>
            <div className="ranking-chart__tooltip-gene">{primaryGeneLabel(denseHoverRanking.gene)}</div>
            <div className="ranking-chart__tooltip-value">{formatTpm(denseHoverRanking.total)} TPM</div>
            <div className="ranking-chart__tooltip-row mono">{denseHoverRanking.gene.canonical_gene_id}</div>
            <div className="ranking-chart__tooltip-row">rank #{(denseHover.index + 1).toLocaleString("en-US")} of {rankings.length.toLocaleString("en-US")}</div>
            {denseHoverRanking.segments.map((seg) => (
              <div className="ranking-chart__tooltip-row" key={seg.bioproject}>
                <span className="ranking-chart__legend-dot" style={{ background: datasetColor(seg.bioproject), display: "inline-block", marginRight: 6 }} />
                {seg.bioproject}: {formatTpm(seg.tpm)} TPM
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
