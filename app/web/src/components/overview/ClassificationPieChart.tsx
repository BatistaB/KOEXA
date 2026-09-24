import { useMemo, useRef, useState } from "react";
import type { Gene, GeneClassification } from "../../data/types";
import { summarizeClassification, type ClassificationSlice } from "../../lib/classificationSummary";
import "./ClassificationPieChart.css";

interface ClassificationPieChartProps {
  classification: Map<string, GeneClassification>;
  genes: Gene[];
  onSelectGene: (gene: Gene) => void;
}

const SIZE = 220;
const CENTER = SIZE / 2;
const OUTER_R = 100;
const INNER_R = 62;

function arcPath(startAngle: number, endAngle: number): string {
  const point = (r: number, a: number): [number, number] => [CENTER + r * Math.sin(a), CENTER - r * Math.cos(a)];
  const [x1, y1] = point(OUTER_R, startAngle);
  const [x2, y2] = point(OUTER_R, endAngle);
  const [x3, y3] = point(INNER_R, endAngle);
  const [x4, y4] = point(INNER_R, startAngle);
  const largeArc = endAngle - startAngle > Math.PI ? 1 : 0;
  return [
    `M ${x1} ${y1}`,
    `A ${OUTER_R} ${OUTER_R} 0 ${largeArc} 1 ${x2} ${y2}`,
    `L ${x3} ${y3}`,
    `A ${INNER_R} ${INNER_R} 0 ${largeArc} 0 ${x4} ${y4}`,
    "Z",
  ].join(" ");
}

/** One representative gene per slice (highest median TPM in that
 * category), so clicking a legend row can jump somewhere concrete. */
function topGeneForLabel(
  key: ClassificationSlice["key"],
  classification: Map<string, GeneClassification>,
  genesById: Map<string, Gene>,
): Gene | null {
  let best: { gene: Gene; tpm: number } | null = null;
  for (const entry of classification.values()) {
    const entryKey = entry.biological_label ?? "unclassified";
    if (entryKey !== key) continue;
    const gene = genesById.get(entry.canonical_gene_id);
    if (!gene) continue;
    if (!best || entry.median_TPM > best.tpm) best = { gene, tpm: entry.median_TPM };
  }
  return best?.gene ?? null;
}

export function ClassificationPieChart({ classification, genes, onSelectGene }: ClassificationPieChartProps) {
  const [hovered, setHovered] = useState<ClassificationSlice["key"] | null>(null);
  const [tooltip, setTooltip] = useState<{ x: number; y: number; slice: ClassificationSlice } | null>(null);
  const canvasRef = useRef<HTMLDivElement>(null);

  const slices = useMemo(() => summarizeClassification(classification), [classification]);
  const total = useMemo(() => slices.reduce((sum, s) => sum + s.count, 0), [slices]);
  const genesById = useMemo(() => new Map(genes.map((g) => [g.canonical_gene_id, g])), [genes]);

  if (slices.length === 0) {
    return (
      <section className="classification-pie">
        <div className="classification-pie__title">Gene expression classification</div>
        <p className="classification-pie__empty">
          No classification data yet — run <code>atlas cluster genes</code> and re-export to populate this chart.
        </p>
      </section>
    );
  }

  const arcs: { slice: ClassificationSlice; start: number; end: number }[] = [];
  let cursor = 0;
  for (const slice of slices) {
    const sweep = slice.fraction * Math.PI * 2;
    arcs.push({ slice, start: cursor, end: cursor + sweep });
    cursor += sweep;
  }

  const showTooltip = (slice: ClassificationSlice, target: Element) => {
    const canvasRect = canvasRef.current?.getBoundingClientRect();
    const targetRect = target.getBoundingClientRect();
    if (!canvasRect) return;
    setTooltip({
      x: targetRect.left + targetRect.width / 2 - canvasRect.left,
      y: targetRect.top - canvasRect.top,
      slice,
    });
  };

  const handleSelect = (key: ClassificationSlice["key"]) => {
    const gene = topGeneForLabel(key, classification, genesById);
    if (gene) onSelectGene(gene);
  };

  return (
    <section className="classification-pie">
      <div className="classification-pie__title">Gene expression classification</div>
      <p className="classification-pie__subtitle">
        {total.toLocaleString("en-US")} genes classified by expression behavior (Tau specificity + abundance/
        prevalence/variability, unsupervised clustering — see the gene's "Expression behavior" panel for detail).
        Preliminary: based on the atlas's current sample/condition coverage and will sharpen as more studies are
        added.
      </p>

      <div className="classification-pie__body">
        <div className="classification-pie__canvas" ref={canvasRef}>
          <svg
            className="classification-pie__svg"
            viewBox={`0 0 ${SIZE} ${SIZE}`}
            role="img"
            aria-label="Gene expression classification breakdown"
          >
            {arcs.map(({ slice, start, end }) => (
              <path
                key={slice.key}
                d={arcPath(start, end)}
                fill={slice.color}
                stroke="var(--surface-2)"
                strokeWidth={2}
                opacity={hovered === null || hovered === slice.key ? 1 : 0.45}
                className="classification-pie__arc"
                tabIndex={0}
                role="button"
                aria-label={`${slice.label}: ${slice.count.toLocaleString("en-US")} genes (${(slice.fraction * 100).toFixed(1)}%)`}
                onMouseEnter={(e) => {
                  setHovered(slice.key);
                  showTooltip(slice, e.currentTarget);
                }}
                onMouseLeave={() => {
                  setHovered(null);
                  setTooltip(null);
                }}
                onFocus={(e) => {
                  setHovered(slice.key);
                  showTooltip(slice, e.currentTarget);
                }}
                onBlur={() => {
                  setHovered(null);
                  setTooltip(null);
                }}
                onClick={() => handleSelect(slice.key)}
                onKeyDown={(e) => {
                  if (e.key === "Enter" || e.key === " ") {
                    e.preventDefault();
                    handleSelect(slice.key);
                  }
                }}
              />
            ))}
          </svg>
          <div className="classification-pie__center">
            <span className="classification-pie__center-value">{total.toLocaleString("en-US")}</span>
            <span className="classification-pie__center-label">genes</span>
          </div>
          {tooltip && (
            <div
              className="classification-pie__tooltip"
              style={{ left: tooltip.x, top: tooltip.y }}
            >
              <div className="classification-pie__tooltip-label">{tooltip.slice.label}</div>
              <div className="classification-pie__tooltip-value">
                {tooltip.slice.count.toLocaleString("en-US")} genes · {(tooltip.slice.fraction * 100).toFixed(1)}%
              </div>
            </div>
          )}
        </div>

        <ul className="classification-pie__legend">
          {slices.map((slice) => (
            <li key={slice.key}>
              <button
                type="button"
                className="classification-pie__legend-item"
                onMouseEnter={() => setHovered(slice.key)}
                onMouseLeave={() => setHovered(null)}
                onClick={() => handleSelect(slice.key)}
              >
                <span className="classification-pie__legend-dot" style={{ background: slice.color }} />
                <span className="classification-pie__legend-label">{slice.label}</span>
                <span className="classification-pie__legend-count">
                  {slice.count.toLocaleString("en-US")} · {(slice.fraction * 100).toFixed(1)}%
                </span>
              </button>
            </li>
          ))}
        </ul>
      </div>
    </section>
  );
}
