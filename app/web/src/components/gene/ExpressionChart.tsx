import { useMemo, useRef, useState } from "react";
import type { ChartPoint } from "./chartTypes";
import { logTicks, niceLinearTicks } from "../../lib/chartScale";
import { shortConditionLabel } from "../../lib/conditionLabel";
import { formatTpm } from "../../lib/format";
import { truncateLabel } from "../../lib/geneDisplay";
import { roundedTopBarPath } from "../../lib/barPath";
import { DatasetLink } from "../common/DatasetLink";
import "./ExpressionChart.css";

/** Max characters of a condition label drawn on the x axis; the full text
 * stays available as a hover tooltip and in the sample table. */
const X_TICK_MAX_CHARS = 40;

export type ChartScale = "linear" | "log";

interface ExpressionChartProps {
  points: ChartPoint[];
  datasetColor: (bioproject: string) => string;
  scale: ChartScale;
  onScaleChange: (scale: ChartScale) => void;
  selectedSampleId: string | null;
  hoveredSampleId: string | null;
  onHoverSample: (id: string | null) => void;
  onSelectSample: (id: string) => void;
  onSelectDataset: (bioproject: string) => void;
}

const VB_W = 900;
const VB_H = 320;
const MARGIN = { top: 16, right: 20, bottom: 66, left: 50 };
const INNER_W = VB_W - MARGIN.left - MARGIN.right;
const INNER_H = VB_H - MARGIN.top - MARGIN.bottom;

export function ExpressionChart({
  points,
  datasetColor,
  scale,
  onScaleChange,
  selectedSampleId,
  hoveredSampleId,
  onHoverSample,
  onSelectSample,
  onSelectDataset,
}: ExpressionChartProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [tooltip, setTooltip] = useState<{ point: ChartPoint; x: number; y: number } | null>(null);

  const datasets = useMemo(() => {
    const seen = new Map<string, string>();
    for (const p of points) {
      if (!seen.has(p.sample.bioproject)) {
        seen.set(p.sample.bioproject, p.dataset?.publication_title ?? p.sample.bioproject);
      }
    }
    return Array.from(seen.entries());
  }, [points]);

  const groupOrder = useMemo(() => {
    const order: string[] = [];
    for (const p of points) {
      if (!order.includes(p.condition.condition_id)) order.push(p.condition.condition_id);
    }
    return order;
  }, [points]);

  const groups = useMemo(() => {
    return groupOrder.map((conditionId) => {
      const groupPoints = points
        .filter((p) => p.condition.condition_id === conditionId)
        .sort((a, b) => a.sample.biological_replicate - b.sample.biological_replicate);
      const mean = groupPoints.reduce((sum, p) => sum + p.tpm, 0) / (groupPoints.length || 1);
      return { conditionId, condition: groupPoints[0]?.condition, points: groupPoints, mean };
    });
  }, [groupOrder, points]);

  const yMaxRaw = Math.max(1, ...points.map((p) => p.tpm));
  const yMax = yMaxRaw * 1.12;

  const yScale = (tpm: number): number => {
    if (scale === "log") {
      const domainMax = Math.log10(yMax + 1);
      return INNER_H - (Math.log10(tpm + 1) / domainMax) * INNER_H;
    }
    return INNER_H - (tpm / yMax) * INNER_H;
  };

  const ticks = scale === "log" ? logTicks(yMax) : niceLinearTicks(yMax);

  const bandWidth = INNER_W / Math.max(1, groups.length);

  const showTooltip = (point: ChartPoint, target: Element) => {
    const containerRect = containerRef.current?.getBoundingClientRect();
    const targetRect = target.getBoundingClientRect();
    if (!containerRect) return;
    setTooltip({
      point,
      x: targetRect.left + targetRect.width / 2 - containerRect.left,
      y: targetRect.top + targetRect.height / 2 - containerRect.top,
    });
    onHoverSample(point.sample.sample_id);
  };

  const clearTooltip = () => {
    setTooltip(null);
    onHoverSample(null);
  };

  return (
    <div className="expr-chart">
      <div className="expr-chart__controls">
        <div className="expr-chart__legend">
          {datasets.map(([bioproject, title]) => (
            <span className="expr-chart__legend-item" key={bioproject} title={title}>
              <span
                className="expr-chart__legend-dot"
                style={{ background: datasetColor(bioproject) }}
              />
              <DatasetLink bioproject={bioproject} onSelect={onSelectDataset} />
            </span>
          ))}
        </div>
        <div className="expr-chart__toggle-group" role="group" aria-label="Y-axis scale">
          <button
            type="button"
            className="expr-chart__toggle"
            aria-pressed={scale === "linear"}
            onClick={() => onScaleChange("linear")}
          >
            Linear
          </button>
          <button
            type="button"
            className="expr-chart__toggle"
            aria-pressed={scale === "log"}
            onClick={() => onScaleChange("log")}
          >
            Log10
          </button>
        </div>
      </div>

      <div className="expr-chart__canvas" ref={containerRef}>
        <svg
          className="expr-chart__svg"
          viewBox={`0 0 ${VB_W} ${VB_H}`}
          preserveAspectRatio="xMidYMid meet"
          role="img"
          aria-label={`Expression (TPM) per sample, grouped by condition, ${scale} scale`}
        >
          <g transform={`translate(${MARGIN.left},${MARGIN.top})`}>
            {/* gridlines + y ticks */}
            {ticks.map((t) => (
              <g key={t}>
                <line
                  x1={0}
                  x2={INNER_W}
                  y1={yScale(t)}
                  y2={yScale(t)}
                  stroke="var(--chart-gridline)"
                  strokeWidth={1}
                />
                <text x={-8} y={yScale(t)} textAnchor="end" dominantBaseline="middle" className="expr-chart__tick-label">
                  {t.toLocaleString("en-US")}
                </text>
              </g>
            ))}

            {/* y axis label */}
            <text
              className="expr-chart__axis-label"
              transform={`translate(${-MARGIN.left + 14}, ${INNER_H / 2}) rotate(-90)`}
              textAnchor="middle"
            >
              TPM{scale === "log" ? " (log10)" : ""}
            </text>

            {/* baseline */}
            <line x1={0} x2={INNER_W} y1={INNER_H} y2={INNER_H} stroke="var(--chart-axis)" strokeWidth={1} />

            {groups.map((group, gi) => {
              const centerX = gi * bandWidth + bandWidth / 2;
              const n = group.points.length;
              const spacing = Math.min(16, bandWidth / (n + 1));
              return (
                <g key={group.conditionId}>
                  {/* mean tick */}
                  <line
                    className="expr-chart__mean-tick"
                    x1={centerX - bandWidth * 0.3}
                    x2={centerX + bandWidth * 0.3}
                    y1={yScale(group.mean)}
                    y2={yScale(group.mean)}
                    stroke="var(--text-secondary)"
                    strokeWidth={1.5}
                    strokeDasharray="3,2"
                  />

                  {/* x tick label */}
                  <text
                    className="expr-chart__x-tick-label"
                    x={centerX}
                    y={INNER_H + 14}
                    textAnchor="end"
                    transform={`rotate(-28, ${centerX}, ${INNER_H + 14})`}
                  >
                    {(() => {
                      const full = group.condition ? shortConditionLabel(group.condition) : group.conditionId;
                      return (
                        <>
                          <title>{full}</title>
                          {truncateLabel(full, X_TICK_MAX_CHARS)}
                        </>
                      );
                    })()}
                  </text>

                  {group.points.map((point, idx) => {
                    const cx = centerX + (idx - (n - 1) / 2) * spacing;
                    const barWidth = Math.min(20, spacing * 0.72);
                    const barX = cx - barWidth / 2;
                    const barY = yScale(point.tpm);
                    const barHeight = INNER_H - barY;
                    const id = point.sample.sample_id;
                    const isSelected = id === selectedSampleId;
                    const isHovered = id === hoveredSampleId;
                    const flagged = point.sample.qc_status === "warning";
                    const color = datasetColor(point.sample.bioproject);
                    const hitWidth = Math.max(barWidth + 8, 18);
                    return (
                      <g
                        key={id}
                        tabIndex={0}
                        role="button"
                        aria-label={`${id}, ${formatTpm(point.tpm)} TPM${flagged ? ", QC warning" : ""}`}
                        onMouseMove={(e) => showTooltip(point, e.currentTarget)}
                        onMouseLeave={clearTooltip}
                        onFocus={(e) => showTooltip(point, e.currentTarget)}
                        onBlur={clearTooltip}
                        onClick={() => onSelectSample(id)}
                        onKeyDown={(e) => {
                          if (e.key === "Enter" || e.key === " ") {
                            e.preventDefault();
                            onSelectSample(id);
                          }
                        }}
                      >
                        <rect
                          className="expr-chart__hit"
                          x={cx - hitWidth / 2}
                          y={0}
                          width={hitWidth}
                          height={INNER_H}
                        />
                        <path
                          className="expr-chart__bar"
                          d={roundedTopBarPath(barX, barY, barWidth, barHeight, 3)}
                          fill={color}
                          opacity={isHovered || isSelected ? 1 : 0.92}
                          stroke={isSelected ? "var(--accent)" : "none"}
                          strokeWidth={isSelected ? 2 : 0}
                        />
                        {flagged && (
                          <path
                            d={`M ${cx} ${barY - 12} l 4 7 h -8 Z`}
                            fill="var(--status-warning)"
                            stroke="var(--surface-1)"
                            strokeWidth={1}
                          />
                        )}
                      </g>
                    );
                  })}
                </g>
              );
            })}
          </g>
        </svg>

        {tooltip && (
          <div
            className="expr-chart__tooltip"
            style={{ left: tooltip.x, top: tooltip.y - 14 }}
          >
            <div className="expr-chart__tooltip-value">{formatTpm(tooltip.point.tpm)} TPM</div>
            <div className="expr-chart__tooltip-row mono">{tooltip.point.sample.sample_id}</div>
            <div className="expr-chart__tooltip-row">{tooltip.point.sample.bioproject}</div>
            {tooltip.point.sample.qc_status === "warning" && (
              <div className="expr-chart__tooltip-row">⚠ QC warning</div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
