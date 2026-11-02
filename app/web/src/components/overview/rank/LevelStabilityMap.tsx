import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { ExpressionClass, ExpressionRankRow, Gene } from "../../../data/types";
import { CLASS_COLOR_VAR, CLASS_ORDER } from "../../../lib/expressionRank";
import { primaryGeneLabel, truncateLabel } from "../../../lib/geneDisplay";

interface LevelStabilityMapProps {
  rows: ExpressionRankRow[];
  genesById: Map<string, Gene>;
  selectedClass: ExpressionClass | null;
  onSelectGene: (gene: Gene) => void;
}

const HEIGHT = 380;
const MARGIN = { left: 48, right: 14, top: 12, bottom: 44 };
const HIT_RADIUS = 8;

function cssVar(name: string): string {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim() || "#888";
}

/** Every gene as a point: x = how highly it is expressed (percentile of the
 * median), y = how stable it is (percentile of the stability score). The two
 * axes are deliberately independent -- high expression does not imply a
 * stable (constitutive) gene. Canvas, because 12k SVG nodes would make
 * hover sluggish. */
export function LevelStabilityMap({ rows, genesById, selectedClass, onSelectGene }: LevelStabilityMapProps) {
  const wrapRef = useRef<HTMLDivElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const overlayRef = useRef<HTMLCanvasElement>(null);
  const [width, setWidth] = useState(560);
  const [themeTick, setThemeTick] = useState(0);
  const [hover, setHover] = useState<{ row: ExpressionRankRow; x: number; y: number } | null>(null);

  useEffect(() => {
    const el = wrapRef.current;
    if (!el) return;
    const observer = new ResizeObserver(() => setWidth(Math.max(320, Math.floor(el.clientWidth))));
    observer.observe(el);
    setWidth(Math.max(320, Math.floor(el.clientWidth)));
    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    const media = window.matchMedia("(prefers-color-scheme: dark)");
    const onChange = () => setThemeTick((t) => t + 1);
    media.addEventListener("change", onChange);
    const mutation = new MutationObserver(onChange);
    mutation.observe(document.documentElement, { attributes: true, attributeFilter: ["data-theme"] });
    return () => {
      media.removeEventListener("change", onChange);
      mutation.disconnect();
    };
  }, []);

  const plotW = width - MARGIN.left - MARGIN.right;
  const plotH = HEIGHT - MARGIN.top - MARGIN.bottom;
  const toX = useCallback((score: number) => MARGIN.left + score * plotW, [plotW]);
  const toY = useCallback((score: number) => MARGIN.top + (1 - score) * plotH, [plotH]);

  const medians = useMemo(() => {
    const byClass = new Map<ExpressionClass, { x: number[]; y: number[] }>();
    for (const r of rows) {
      const entry = byClass.get(r.expression_class) ?? { x: [], y: [] };
      entry.x.push(r.level_score);
      entry.y.push(r.stability_score);
      byClass.set(r.expression_class, entry);
    }
    const median = (v: number[]) => [...v].sort((a, b) => a - b)[Math.floor(v.length / 2)];
    return CLASS_ORDER.filter((c) => byClass.has(c)).map((c) => ({
      cls: c,
      x: median(byClass.get(c)!.x),
      y: median(byClass.get(c)!.y),
    }));
  }, [rows]);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const dpr = window.devicePixelRatio || 1;
    canvas.width = width * dpr;
    canvas.height = HEIGHT * dpr;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, width, HEIGHT);

    const grid = cssVar("--chart-gridline");
    const axis = cssVar("--chart-axis");
    const muted = cssVar("--text-muted");
    const surface = cssVar("--surface-1");
    const text = cssVar("--text-secondary");
    ctx.font = "11px Inter, system-ui, sans-serif";

    ctx.strokeStyle = grid;
    ctx.lineWidth = 1;
    ctx.fillStyle = muted;
    for (const tick of [0, 0.25, 0.5, 0.75, 1]) {
      ctx.beginPath();
      ctx.moveTo(toX(tick), MARGIN.top);
      ctx.lineTo(toX(tick), MARGIN.top + plotH);
      ctx.moveTo(MARGIN.left, toY(tick));
      ctx.lineTo(MARGIN.left + plotW, toY(tick));
      ctx.stroke();
      ctx.textAlign = "center";
      ctx.fillText(`${Math.round(tick * 100)}`, toX(tick), MARGIN.top + plotH + 16);
      ctx.textAlign = "right";
      ctx.fillText(`${Math.round(tick * 100)}`, MARGIN.left - 8, toY(tick) + 4);
    }
    ctx.strokeStyle = axis;
    ctx.strokeRect(MARGIN.left, MARGIN.top, plotW, plotH);
    ctx.fillStyle = text;
    ctx.textAlign = "center";
    ctx.fillText("Expression level (percentile of median TPM)", MARGIN.left + plotW / 2, HEIGHT - 8);
    ctx.save();
    ctx.translate(13, MARGIN.top + plotH / 2);
    ctx.rotate(-Math.PI / 2);
    ctx.fillText("Stability (percentile)", 0, 0);
    ctx.restore();

    const colors = Object.fromEntries(CLASS_ORDER.map((c) => [c, cssVar(CLASS_COLOR_VAR[c])])) as Record<ExpressionClass, string>;
    const backdrop = cssVar("--border-hairline");
    const drawPoints = (predicate: (r: ExpressionRankRow) => boolean, color: (r: ExpressionRankRow) => string, radius: number, alpha: number) => {
      ctx.globalAlpha = alpha;
      for (const r of rows) {
        if (!predicate(r)) continue;
        ctx.fillStyle = color(r);
        ctx.beginPath();
        ctx.arc(toX(r.level_score), toY(r.stability_score), radius, 0, Math.PI * 2);
        ctx.fill();
      }
      ctx.globalAlpha = 1;
    };

    if (selectedClass === null) {
      drawPoints(() => true, (r) => colors[r.expression_class], 1.7, 0.55);
    } else {
      drawPoints((r) => r.expression_class !== selectedClass, () => backdrop, 1.5, 0.9);
      drawPoints((r) => r.expression_class === selectedClass, () => colors[selectedClass], 2.1, 0.8);
    }

    // Direct labels at each class' median position (identity never relies on color alone). Labels that would
    // collide are nudged vertically; if no free slot is found they are skipped (the class list names them too).
    ctx.font = "600 11px Inter, system-ui, sans-serif";
    ctx.textAlign = "center";
    const placed: { x0: number; x1: number; y0: number; y1: number }[] = [];
    for (const m of medians) {
      if (selectedClass !== null && selectedClass !== m.cls) continue;
      const w = ctx.measureText(m.cls).width;
      const cx = Math.min(Math.max(toX(m.x), MARGIN.left + w / 2 + 2), MARGIN.left + plotW - w / 2 - 2);
      let cy = toY(m.y);
      let slot = 0;
      const collides = (y: number) => placed.some((b) => cx - w / 2 < b.x1 && cx + w / 2 > b.x0 && y - 12 < b.y1 && y + 3 > b.y0);
      while (collides(cy) && slot < 8) {
        slot += 1;
        cy = toY(m.y) + (slot % 2 === 1 ? 1 : -1) * Math.ceil(slot / 2) * 14;
      }
      if (collides(cy)) continue;
      placed.push({ x0: cx - w / 2, x1: cx + w / 2, y0: cy - 12, y1: cy + 3 });
      ctx.lineWidth = 3;
      ctx.strokeStyle = surface;
      ctx.strokeText(m.cls, cx, cy);
      ctx.fillStyle = text;
      ctx.fillText(m.cls, cx, cy);
    }

  }, [rows, selectedClass, width, plotW, plotH, toX, toY, medians, themeTick]);

  // The hover ring lives on its own canvas, so moving the mouse never redraws the ~12k points underneath.
  useEffect(() => {
    const canvas = overlayRef.current;
    if (!canvas) return;
    const dpr = window.devicePixelRatio || 1;
    canvas.width = width * dpr;
    canvas.height = HEIGHT * dpr;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, width, HEIGHT);
    if (!hover) return;
    ctx.strokeStyle = cssVar("--text-primary");
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.arc(toX(hover.row.level_score), toY(hover.row.stability_score), 5, 0, Math.PI * 2);
    ctx.stroke();
  }, [hover, width, toX, toY, themeTick]);

  const findNearest = (clientX: number, clientY: number) => {
    const rect = canvasRef.current?.getBoundingClientRect();
    if (!rect) return null;
    const px = clientX - rect.left;
    const py = clientY - rect.top;
    let best: ExpressionRankRow | null = null;
    let bestDist = HIT_RADIUS * HIT_RADIUS;
    for (const r of rows) {
      if (selectedClass !== null && r.expression_class !== selectedClass) continue;
      const dx = toX(r.level_score) - px;
      const dy = toY(r.stability_score) - py;
      const d = dx * dx + dy * dy;
      if (d < bestDist) {
        bestDist = d;
        best = r;
      }
    }
    return best ? { row: best, x: toX(best.level_score), y: toY(best.stability_score) } : null;
  };

  const hoverGene = hover ? genesById.get(hover.row.canonical_gene_id) : undefined;

  return (
    <div className="rank-card">
      <div className="rank-card__title">
        Level × stability
        <span className="rank-card__title-meta">each point is a gene</span>
      </div>
      <div className="rank-map" ref={wrapRef}>
        <canvas
          ref={canvasRef}
          className="rank-map__canvas"
          style={{ width: "100%", height: HEIGHT }}
          role="img"
          aria-label="Scatter plot of every gene: expression level percentile against stability percentile, colored by expression class. Use the class list and the top-genes list for keyboard access."
          onMouseMove={(e) => setHover(findNearest(e.clientX, e.clientY))}
          onMouseLeave={() => setHover(null)}
          onClick={(e) => {
            const nearest = findNearest(e.clientX, e.clientY);
            const gene = nearest ? genesById.get(nearest.row.canonical_gene_id) : undefined;
            if (gene) onSelectGene(gene);
          }}
        />
        <canvas ref={overlayRef} className="rank-map__overlay" style={{ width: "100%", height: HEIGHT }} aria-hidden="true" />
        {hover && (
          <div className="rank-tooltip" style={{ left: Math.min(hover.x + 12, width - 230), top: Math.max(hover.y - 8, 4) }}>
            <div className="rank-tooltip__title">
              {hoverGene ? truncateLabel(primaryGeneLabel(hoverGene), 34) : hover.row.canonical_gene_id}
            </div>
            <div className="rank-tooltip__row">{hover.row.expression_class}</div>
            <div className="rank-tooltip__row">
              level {Math.round(hover.row.level_score * 100)} · stability {Math.round(hover.row.stability_score * 100)} · median{" "}
              {hover.row.median_TPM.toFixed(hover.row.median_TPM < 10 ? 2 : 0)} TPM
            </div>
            <div className="rank-tooltip__hint">click to open the gene</div>
          </div>
        )}
      </div>
      <p className="rank-card__hint">
        Level and stability are separate scores: a highly expressed gene can still be unstable, which is why it is not automatically called constitutive.
      </p>
    </div>
  );
}
