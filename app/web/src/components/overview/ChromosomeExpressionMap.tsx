import { useMemo, useRef, useState } from "react";
import type {
  ChromosomeBin,
  ChromosomeExpression,
  Condition,
  Dataset,
  Gene,
  GeneClassification,
  GeneExpressionRow,
  Sample,
} from "../../data/types";
import { RAMP_STEPS, sequentialColor, sequentialColorIndex } from "../../lib/sequentialColor";
import { buildGeneRankings } from "../../lib/points";
import { GeneRankingChart } from "./GeneRankingChart";
import "./ChromosomeExpressionMap.css";

interface ChromosomeExpressionMapProps {
  chromosomeExpression: ChromosomeExpression | null;
  genes: Gene[];
  classification: Map<string, GeneClassification>;
  samples: Sample[];
  conditions: Condition[];
  datasets: Dataset[];
  geneExpression: GeneExpressionRow[];
  strainFilter: string;
  conditionFilter: string;
  datasetColor: (bioproject: string) => string;
  onSelectGene: (gene: Gene) => void;
  onSelectDataset: (bioproject: string) => void;
}

const MAX_TRACK_HEIGHT = 480;
const COLUMN_WIDTH = 56;

function shortChromosomeLabel(chromosome: string): string {
  return chromosome.replace("_A_oryzae_RIB40", "").replace("Chr", "Chr ");
}

interface HoverState {
  x: number;
  y: number;
  chromosome: string;
  bin: ChromosomeBin;
  topGenes: { gene: Gene; medianTpm: number }[];
}

interface SelectedBin {
  chromosome: string;
  start: number;
  end: number;
}

/** null = show every region normally; a number = show only bins in that
 * sequential-color bucket (0 = lowest, RAMP_STEPS.length-1 = highest);
 * "empty" = show only bins with no annotated genes. Everything else dims,
 * rather than disappearing, so the karyotype shape stays visible. */
type LevelFilter = number | "empty" | null;

function genesInBin(genes: Gene[], chromosome: string, start: number, end: number): Gene[] {
  return genes.filter((g) => {
    if (g.chromosome !== chromosome) return false;
    const mid = (g.start + g.end) / 2;
    return mid >= start && mid < end;
  });
}

export function ChromosomeExpressionMap({
  chromosomeExpression,
  genes,
  classification,
  samples,
  conditions,
  datasets,
  geneExpression,
  strainFilter,
  conditionFilter,
  datasetColor,
  onSelectGene,
  onSelectDataset,
}: ChromosomeExpressionMapProps) {
  const [hover, setHover] = useState<HoverState | null>(null);
  const [selectedBin, setSelectedBin] = useState<SelectedBin | null>(null);
  const [levelFilter, setLevelFilter] = useState<LevelFilter>(null);
  const canvasRef = useRef<HTMLDivElement>(null);

  const maxLog10 = useMemo(() => {
    if (!chromosomeExpression) return 0;
    let max = 0;
    for (const track of chromosomeExpression.chromosomes) {
      for (const bin of track.bins) {
        if (bin.log10MeanTpm !== null && bin.log10MeanTpm > max) max = bin.log10MeanTpm;
      }
    }
    return max;
  }, [chromosomeExpression]);

  const maxLength = useMemo(() => {
    if (!chromosomeExpression) return 1;
    return Math.max(1, ...chromosomeExpression.chromosomes.map((t) => t.length));
  }, [chromosomeExpression]);

  const regionGenes = useMemo(
    () => (selectedBin ? genesInBin(genes, selectedBin.chromosome, selectedBin.start, selectedBin.end) : []),
    [genes, selectedBin],
  );

  const regionRankings = useMemo(
    () =>
      selectedBin
        ? buildGeneRankings(regionGenes, samples, conditions, datasets, geneExpression, strainFilter, conditionFilter)
        : [],
    [selectedBin, regionGenes, samples, conditions, datasets, geneExpression, strainFilter, conditionFilter],
  );

  const regionVisibleDatasets = useMemo((): [string, string][] => {
    const seen = new Map<string, string>();
    for (const ranking of regionRankings) {
      for (const seg of ranking.segments) {
        if (!seen.has(seg.bioproject)) {
          const ds = datasets.find((d) => d.bioproject === seg.bioproject);
          seen.set(seg.bioproject, ds?.publication_title ?? seg.bioproject);
        }
      }
    }
    return Array.from(seen.entries());
  }, [regionRankings, datasets]);

  if (!chromosomeExpression || chromosomeExpression.chromosomes.length === 0) {
    return (
      <section className="chromosome-map">
        <div className="chromosome-map__title">Expression by chromosome location</div>
        <p className="chromosome-map__empty">
          No chromosome map data yet — run <code>atlas stats genes</code> and re-export to populate this view.
        </p>
      </section>
    );
  }

  const pxPerBp = MAX_TRACK_HEIGHT / maxLength;

  const showHover = (chromosome: string, bin: ChromosomeBin, target: Element) => {
    const canvasRect = canvasRef.current?.getBoundingClientRect();
    const targetRect = target.getBoundingClientRect();
    if (!canvasRect) return;
    const binGenes = genesInBin(genes, chromosome, bin.start, bin.end)
      .map((gene) => ({ gene, medianTpm: classification.get(gene.canonical_gene_id)?.median_TPM ?? 0 }))
      .sort((a, b) => b.medianTpm - a.medianTpm)
      .slice(0, 5);
    setHover({
      x: targetRect.left + targetRect.width / 2 - canvasRect.left,
      y: targetRect.top - canvasRect.top,
      chromosome,
      bin,
      topGenes: binGenes,
    });
  };

  const handleClick = (chromosome: string, bin: ChromosomeBin) => {
    if (bin.nGenes === 0) return;
    setHover(null);
    setSelectedBin({ chromosome, start: bin.start, end: bin.end });
  };

  const binMatchesFilter = (bin: ChromosomeBin): boolean => {
    if (levelFilter === null) return true;
    if (levelFilter === "empty") return bin.nGenes === 0;
    if (bin.nGenes === 0 || bin.log10MeanTpm === null) return false;
    return sequentialColorIndex(bin.log10MeanTpm, maxLog10) === levelFilter;
  };

  const toggleLevelFilter = (level: LevelFilter) => {
    setLevelFilter((current) => (current === level ? null : level));
  };

  if (selectedBin) {
    return (
      <section className="chromosome-map">
        <div className="chromosome-map__region-header">
          <button type="button" className="chromosome-map__back" onClick={() => setSelectedBin(null)}>
            ← Back to chromosome map
          </button>
          <div className="chromosome-map__region-title">
            {shortChromosomeLabel(selectedBin.chromosome)}:{selectedBin.start.toLocaleString("en-US")}-
            {selectedBin.end.toLocaleString("en-US")}
            <span className="chromosome-map__region-count">
              {regionGenes.length.toLocaleString("en-US")} gene{regionGenes.length === 1 ? "" : "s"} in this window
            </span>
          </div>
        </div>
        {regionRankings.length > 0 ? (
          <GeneRankingChart
            rankings={regionRankings}
            datasets={regionVisibleDatasets}
            datasetColor={datasetColor}
            onSelectGene={onSelectGene}
            onSelectDataset={onSelectDataset}
          />
        ) : (
          <p className="chromosome-map__empty">No genes annotated in this window.</p>
        )}
      </section>
    );
  }

  return (
    <section className="chromosome-map">
      <div className="chromosome-map__title">Expression by chromosome location</div>
      <p className="chromosome-map__subtitle">
        RIB40's 8 nuclear chromosomes, binned into {(chromosomeExpression.binSizeBp / 1000).toFixed(0)}kb windows and
        colored by mean TPM across all genes in the window — whole-atlas median expression, every curated sample and
        condition. Hover a region to preview its genes; click to see all of them ranked, most to least expressed.
        Click a swatch in the legend below to filter the map to just that expression level.
      </p>

      <div className="chromosome-map__canvas" ref={canvasRef}>
        {chromosomeExpression.chromosomes.map((track) => {
          const trackHeight = track.length * pxPerBp;
          return (
            <div className="chromosome-map__column" key={track.chromosome}>
              <span className="chromosome-map__column-label">{shortChromosomeLabel(track.chromosome)}</span>
              <svg
                className="chromosome-map__track"
                width={COLUMN_WIDTH}
                height={trackHeight}
                viewBox={`0 0 ${COLUMN_WIDTH} ${trackHeight}`}
              >
                <rect x={0} y={0} width={COLUMN_WIDTH} height={trackHeight} rx={3} className="chromosome-map__track-bg" />
                {track.bins.map((bin) => {
                  const y = bin.start * pxPerBp;
                  const h = Math.max(0.5, (bin.end - bin.start) * pxPerBp);
                  const fill =
                    bin.nGenes === 0 || bin.log10MeanTpm === null
                      ? "var(--surface-sunken)"
                      : sequentialColor(bin.log10MeanTpm, maxLog10);
                  const isHovered = hover?.chromosome === track.chromosome && hover.bin.start === bin.start;
                  return (
                    <rect
                      key={bin.start}
                      x={0}
                      y={y}
                      width={COLUMN_WIDTH}
                      height={h}
                      fill={fill}
                      opacity={binMatchesFilter(bin) ? 1 : 0.12}
                      className="chromosome-map__bin"
                      stroke={isHovered ? "var(--accent)" : "none"}
                      strokeWidth={isHovered ? 1.5 : 0}
                      onMouseEnter={(e) => showHover(track.chromosome, bin, e.currentTarget)}
                      onMouseLeave={() => setHover(null)}
                      onClick={() => handleClick(track.chromosome, bin)}
                    />
                  );
                })}
              </svg>
              <span className="chromosome-map__column-length">{(track.length / 1_000_000).toFixed(1)} Mb</span>
            </div>
          );
        })}
      </div>

      <div className="chromosome-map__legend">
        <span className="chromosome-map__legend-label">Low</span>
        <div className="chromosome-map__ramp">
          {RAMP_STEPS.map((color, level) => (
            <button
              key={level}
              type="button"
              className="chromosome-map__ramp-swatch"
              style={{ background: color }}
              aria-pressed={levelFilter === level}
              aria-label={`Show only regions in expression level ${level + 1} of ${RAMP_STEPS.length}`}
              title="Click to show only this expression level"
              onClick={() => toggleLevelFilter(level)}
            />
          ))}
        </div>
        <span className="chromosome-map__legend-label">High</span>
        <span className="chromosome-map__legend-sep" />
        <button
          type="button"
          className="chromosome-map__legend-swatch chromosome-map__legend-swatch--empty"
          aria-pressed={levelFilter === "empty"}
          title="Click to show only regions with no annotated genes"
          onClick={() => toggleLevelFilter("empty")}
        />
        <span className="chromosome-map__legend-label">No annotated genes</span>
        {levelFilter !== null && (
          <button type="button" className="chromosome-map__legend-reset" onClick={() => setLevelFilter(null)}>
            Show all
          </button>
        )}
      </div>

      {hover && (
        <div className="chromosome-map__tooltip" style={{ left: hover.x, top: hover.y }}>
          <div className="chromosome-map__tooltip-title">
            {shortChromosomeLabel(hover.chromosome)}:{hover.bin.start.toLocaleString("en-US")}-
            {hover.bin.end.toLocaleString("en-US")}
          </div>
          {hover.bin.nGenes === 0 ? (
            <div className="chromosome-map__tooltip-row">No annotated genes in this window.</div>
          ) : (
            <>
              <div className="chromosome-map__tooltip-row">
                {hover.bin.nGenes} genes · {hover.bin.nDetectedGenes} detected · mean{" "}
                {hover.bin.meanTpm?.toFixed(1) ?? "—"} TPM
              </div>
              {hover.topGenes.length > 0 && (
                <div className="chromosome-map__tooltip-genes">
                  {hover.topGenes.map(({ gene, medianTpm }) => (
                    <div key={gene.canonical_gene_id} className="chromosome-map__tooltip-gene">
                      <span>{gene.gene_symbol ?? gene.canonical_gene_id}</span>
                      <span className="mono">{medianTpm.toFixed(1)}</span>
                    </div>
                  ))}
                </div>
              )}
              <div className="chromosome-map__tooltip-hint">Click to see all genes ranked</div>
            </>
          )}
        </div>
      )}
    </section>
  );
}
