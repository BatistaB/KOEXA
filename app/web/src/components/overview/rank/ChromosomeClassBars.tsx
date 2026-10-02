import { useMemo, useState } from "react";
import type { ExpressionClass, ExpressionRankRow, Gene } from "../../../data/types";
import { CLASS_ORDER, chromosomeComposition, classColor } from "../../../lib/expressionRank";

interface ChromosomeClassBarsProps {
  genes: Gene[];
  byGene: Map<string, ExpressionRankRow>;
  chromosomeOrder: string[];
  selectedClass: ExpressionClass | null;
  onSelectClass: (cls: ExpressionClass | null) => void;
}

function chromosomeLabel(chromosome: string): string {
  return chromosome.replace("_A_oryzae_RIB40", "").replace("Chr", "Chr ");
}

/** What fraction of each chromosome's genes falls in each class (100% bars). */
export function ChromosomeClassBars({ genes, byGene, chromosomeOrder, selectedClass, onSelectClass }: ChromosomeClassBarsProps) {
  const [tip, setTip] = useState<string | null>(null);
  const composition = useMemo(() => chromosomeComposition(genes, byGene, chromosomeOrder), [genes, byGene, chromosomeOrder]);

  return (
    <div className="rank-card">
      <div className="rank-card__title">
        Classes by chromosome
        <span className="rank-card__title-meta">share of each chromosome's genes</span>
      </div>
      <div className="rank-chrom" role="list">
        {composition.map((entry) => (
          <div className="rank-chrom__row" key={entry.chromosome} role="listitem">
            <span className="rank-chrom__label">{chromosomeLabel(entry.chromosome)}</span>
            <span className="rank-chrom__track">
              {CLASS_ORDER.map((cls) => {
                const count = entry.counts[cls];
                if (count === 0) return null;
                const pct = (count / entry.total) * 100;
                const text = `${chromosomeLabel(entry.chromosome)} · ${cls}: ${count.toLocaleString("en-US")} genes (${pct.toFixed(1)}%)`;
                return (
                  <button
                    key={cls}
                    type="button"
                    className="rank-chrom__seg"
                    style={{
                      width: `${pct}%`,
                      background: classColor(cls),
                      opacity: selectedClass === null || selectedClass === cls ? 1 : 0.25,
                    }}
                    aria-label={text}
                    aria-pressed={selectedClass === cls}
                    onMouseEnter={() => setTip(text)}
                    onMouseLeave={() => setTip(null)}
                    onFocus={() => setTip(text)}
                    onBlur={() => setTip(null)}
                    onClick={() => onSelectClass(selectedClass === cls ? null : cls)}
                  />
                );
              })}
            </span>
            <span className="rank-chrom__n">{entry.total.toLocaleString("en-US")}</span>
          </div>
        ))}
      </div>
      <p className="rank-card__hint rank-chrom__tip" aria-live="polite">
        {tip ?? "Hover a segment for the count; click it to highlight that class everywhere. Colors as in the class list."}
      </p>
    </div>
  );
}
