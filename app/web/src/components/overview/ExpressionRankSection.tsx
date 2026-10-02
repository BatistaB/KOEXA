import { useMemo, useState } from "react";
import type { ExpressionClass, ExpressionRank, Gene } from "../../data/types";
import { CLASS_ORDER } from "../../lib/expressionRank";
import { ChromosomeClassBars } from "./rank/ChromosomeClassBars";
import { ClassComposition } from "./rank/ClassComposition";
import { LevelStabilityMap } from "./rank/LevelStabilityMap";
import { TopGenesPanel } from "./rank/TopGenesPanel";
import "./ExpressionRankSection.css";

interface ExpressionRankSectionProps {
  expressionRank: ExpressionRank;
  genes: Gene[];
  chromosomeOrder: string[];
  onSelectGene: (gene: Gene) => void;
}

/** Homepage section for the pan-transcriptomic expression rank: four
 * coordinated views of the same per-gene table. The class selection is
 * shared state, so one click on a class highlights it everywhere. The rank
 * is global (all samples), so the top-bar strain/condition filters do not
 * apply here -- stated in the header rather than silently ignored. */
export function ExpressionRankSection({ expressionRank, genes, chromosomeOrder, onSelectGene }: ExpressionRankSectionProps) {
  const [selectedClass, setSelectedClass] = useState<ExpressionClass | null>(null);
  const { summary, rows, byGene } = expressionRank;
  const genesById = useMemo(() => new Map(genes.map((g) => [g.canonical_gene_id, g])), [genes]);

  const counts = useMemo(() => {
    if (summary?.class_counts) return summary.class_counts;
    const fallback: Record<string, number> = Object.fromEntries(CLASS_ORDER.map((c) => [c, 0]));
    for (const row of rows) fallback[row.expression_class] += 1;
    return fallback;
  }, [summary, rows]);

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

      <div className="rank-grid">
        <ClassComposition counts={counts} selectedClass={selectedClass} onSelectClass={setSelectedClass} />
        <LevelStabilityMap rows={rows} genesById={genesById} selectedClass={selectedClass} onSelectGene={onSelectGene} />
        <TopGenesPanel rows={rows} genesById={genesById} selectedClass={selectedClass} onSelectGene={onSelectGene} />
        <ChromosomeClassBars
          genes={genes}
          byGene={byGene}
          chromosomeOrder={chromosomeOrder}
          selectedClass={selectedClass}
          onSelectClass={setSelectedClass}
        />
      </div>
    </section>
  );
}
