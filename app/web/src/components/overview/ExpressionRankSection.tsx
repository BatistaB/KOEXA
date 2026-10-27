import { useMemo, useState } from "react";
import type { ExpressionClass, ExpressionRank, ExpressionRankRow, Gene, GeneSets } from "../../data/types";
import { CLASS_ORDER } from "../../lib/expressionRank";
import { geneSetLabel } from "../../lib/geneSets";
import { ChromosomeClassBars } from "./rank/ChromosomeClassBars";
import { ClassComposition } from "./rank/ClassComposition";
import { LevelStabilityMap } from "./rank/LevelStabilityMap";
import { TopGenesPanel } from "./rank/TopGenesPanel";
import "./ExpressionRankSection.css";

interface ExpressionRankSectionProps {
  expressionRank: ExpressionRank;
  genes: Gene[];
  /** Curated gene sets (e.g. the secretome); null when none has been imported. */
  geneSets: GeneSets | null;
  /** The restricting gene set, owned by the page so the "Genes by total expression" ranking above follows it too. */
  activeSet: string | null;
  onActiveSetChange: (name: string | null) => void;
  chromosomeOrder: string[];
  onSelectGene: (gene: Gene) => void;
}

/** Homepage section for the pan-transcriptomic expression rank: four
 * coordinated views of the same per-gene table. The class selection is
 * shared state, so one click on a class highlights it everywhere. The rank
 * is global (all samples), so the top-bar strain/condition filters do not
 * apply here -- stated in the header rather than silently ignored. */
export function ExpressionRankSection({
  expressionRank,
  genes,
  geneSets,
  activeSet,
  onActiveSetChange,
  chromosomeOrder,
  onSelectGene,
}: ExpressionRankSectionProps) {
  const [selectedClass, setSelectedClass] = useState<ExpressionClass | null>(null);
  // Optional overlay: restrict every view to the members of one curated gene set. The classes themselves
  // are always derived from ALL genes; the set only chooses which genes are shown.
  const { summary } = expressionRank;
  const members = activeSet ? (geneSets?.get(activeSet)?.genes ?? null) : null;
  const rows: ExpressionRankRow[] = useMemo(
    () => (members ? expressionRank.rows.filter((r) => members.has(r.canonical_gene_id)) : expressionRank.rows),
    [expressionRank.rows, members],
  );
  const byGene = useMemo(() => (members ? new Map(rows.map((r) => [r.canonical_gene_id, r])) : expressionRank.byGene), [rows, members, expressionRank.byGene]);
  const shownGenes = useMemo(() => (members ? genes.filter((g) => members.has(g.canonical_gene_id)) : genes), [genes, members]);
  const genesById = useMemo(() => new Map(genes.map((g) => [g.canonical_gene_id, g])), [genes]);

  const counts = useMemo(() => {
    if (!members && summary?.class_counts) return summary.class_counts;
    const fallback: Record<string, number> = Object.fromEntries(CLASS_ORDER.map((c) => [c, 0]));
    for (const row of rows) fallback[row.expression_class] += 1;
    return fallback;
  }, [summary, rows, members]);

  const updated = summary?.generated_at ? summary.generated_at.slice(0, 10) : null;

  return (
    <section className="rank-section">
      <div className="rank-section__title">Global expression behavior</div>
      <p className="rank-section__subtitle">
        How every gene behaves across <strong>all</strong> independent samples of the atlas — expression <em>level</em>,{" "}
        <em>stability</em> and <em>specificity</em> are scored separately, so a highly expressed but erratic gene is not
        called constitutive. Preliminary: classes are relative to the current atlas and are re-derived whenever data are
        added. Independent of the strain/condition filters above.
      </p>
      {summary && (
        <ul className="rank-section__chips" aria-label="Atlas scope for this classification">
          <li>{summary.n_samples} independent samples</li>
          <li>{summary.n_studies} studies</li>
          <li>{summary.n_strains} strains</li>
          <li>{summary.n_genes.toLocaleString("en-US")} genes</li>
          {summary.median_robustness_agreement !== null && (
            <li title="Median share of genes that keep their class when a whole study or strain is removed and the thresholds are re-derived">
              {Math.round(summary.median_robustness_agreement * 100)}% median class stability
            </li>
          )}
          {updated && <li>updated {updated}</li>}
        </ul>
      )}

      {geneSets && geneSets.size > 0 && (
        <div className="rank-section__filters" role="group" aria-label="Restrict the views to a curated gene set">
          <span className="rank-section__filters-label">Show</span>
          <button type="button" className={`rank-filter${activeSet === null ? " rank-filter--active" : ""}`} aria-pressed={activeSet === null} onClick={() => onActiveSetChange(null)}>
            All genes
          </button>
          {[...geneSets].map(([name, set]) => (
            <button
              key={name}
              type="button"
              className={`rank-filter${activeSet === name ? " rank-filter--active" : ""}`}
              aria-pressed={activeSet === name}
              title={`${set.description}. Source: ${set.source}`}
              onClick={() => onActiveSetChange(activeSet === name ? null : name)}
            >
              {geneSetLabel(name)} only
              <span className="rank-filter__count">{set.genes.size.toLocaleString("en-US")}</span>
            </button>
          ))}
          {activeSet && (
            <span className="rank-section__filters-note">
              {rows.length.toLocaleString("en-US")} genes shown. Classes were derived from all genes, not from this set.
            </span>
          )}
        </div>
      )}

      <div className="rank-grid">
        <ClassComposition counts={counts} selectedClass={selectedClass} onSelectClass={setSelectedClass} />
        <LevelStabilityMap rows={rows} genesById={genesById} selectedClass={selectedClass} onSelectGene={onSelectGene} />
        <TopGenesPanel rows={rows} genesById={genesById} selectedClass={selectedClass} onSelectGene={onSelectGene} />
        <ChromosomeClassBars
          genes={shownGenes}
          byGene={byGene}
          chromosomeOrder={chromosomeOrder}
          selectedClass={selectedClass}
          onSelectClass={setSelectedClass}
        />
      </div>
    </section>
  );
}
