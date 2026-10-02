import { useMemo, useState } from "react";
import type { ExpressionClass, ExpressionRankRow, Gene } from "../../../data/types";
import { classColor, flagList, FLAG_TEXT, ORDERINGS, type RankOrdering } from "../../../lib/expressionRank";
import { primaryGeneLabel, truncateLabel } from "../../../lib/geneDisplay";

interface TopGenesPanelProps {
  rows: ExpressionRankRow[];
  genesById: Map<string, Gene>;
  selectedClass: ExpressionClass | null;
  onSelectGene: (gene: Gene) => void;
}

const TOP_N = 12;

/** Six independent orderings of the same table. Switching the ordering never
 * recomputes anything: each gene already carries its rank on every axis. */
export function TopGenesPanel({ rows, genesById, selectedClass, onSelectGene }: TopGenesPanelProps) {
  const [ordering, setOrdering] = useState<RankOrdering>("global");
  const def = ORDERINGS.find((o) => o.key === ordering) ?? ORDERINGS[0];

  const top = useMemo(() => {
    const pool = selectedClass ? rows.filter((r) => r.expression_class === selectedClass) : rows;
    return [...pool].sort((a, b) => def.rank(a) - def.rank(b)).slice(0, TOP_N);
  }, [rows, selectedClass, def]);

  return (
    <div className="rank-card">
      <div className="rank-card__title">
        Top genes
        <span className="rank-card__title-meta">{selectedClass ?? "all classes"}</span>
      </div>
      <div className="rank-segmented" role="group" aria-label="Ordering">
        {ORDERINGS.map((o) => (
          <button
            key={o.key}
            type="button"
            className={`rank-segmented__btn${o.key === ordering ? " rank-segmented__btn--active" : ""}`}
            aria-pressed={o.key === ordering}
            onClick={() => setOrdering(o.key)}
          >
            {o.label}
          </button>
        ))}
      </div>
      <p className="rank-card__hint rank-card__hint--tight">{def.description}</p>
      <ol className="rank-top">
        {top.map((row, i) => {
          const gene = genesById.get(row.canonical_gene_id);
          const flags = flagList(row);
          return (
            <li key={row.canonical_gene_id}>
              <button
                type="button"
                className="rank-top__row"
                disabled={!gene}
                onClick={() => gene && onSelectGene(gene)}
                title={flags.length ? flags.map((f) => FLAG_TEXT[f] ?? f).join("\n") : undefined}
              >
                <span className="rank-top__pos">{i + 1}</span>
                <span className="rank-top__dot" style={{ background: classColor(row.expression_class) }} aria-hidden="true" />
                <span className="rank-top__label">
                  {gene ? truncateLabel(primaryGeneLabel(gene), 38) : row.canonical_gene_id}
                  <span className="rank-top__sub">
                    {row.expression_class} · {row.median_TPM >= 10 ? Math.round(row.median_TPM).toLocaleString("en-US") : row.median_TPM.toFixed(2)} TPM
                    {flags.length > 0 && <span className="rank-top__flag" aria-label="quality flags"> ⚑ {flags.length}</span>}
                  </span>
                </span>
                <span className="rank-top__value">{def.value(row)}</span>
              </button>
            </li>
          );
        })}
        {top.length === 0 && <li className="rank-card__hint">No genes in this class.</li>}
      </ol>
    </div>
  );
}
