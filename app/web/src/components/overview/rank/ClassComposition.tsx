import type { ExpressionClass } from "../../../data/types";
import { CLASS_DESCRIPTION, CLASS_ORDER, classColor } from "../../../lib/expressionRank";

interface ClassCompositionProps {
  counts: Record<string, number>;
  selectedClass: ExpressionClass | null;
  onSelectClass: (cls: ExpressionClass | null) => void;
}

/** Class composition as labeled horizontal bars: with 7 classes a bar list
 * reads better than a donut (identity is the row label, not a color). */
export function ClassComposition({ counts, selectedClass, onSelectClass }: ClassCompositionProps) {
  const total = CLASS_ORDER.reduce((sum, c) => sum + (counts[c] ?? 0), 0);
  const max = Math.max(1, ...CLASS_ORDER.map((c) => counts[c] ?? 0));

  return (
    <div className="rank-card">
      <div className="rank-card__title">
        Classes
        <span className="rank-card__title-meta">{total.toLocaleString("en-US")} genes</span>
      </div>
      <ul className="rank-classes" aria-label="Expression classes">
        {CLASS_ORDER.map((cls) => {
          const count = counts[cls] ?? 0;
          const dimmed = selectedClass !== null && selectedClass !== cls;
          return (
            <li key={cls}>
              <button
                type="button"
                className={`rank-classes__row${selectedClass === cls ? " rank-classes__row--selected" : ""}`}
                style={{ opacity: dimmed ? 0.45 : 1 }}
                aria-pressed={selectedClass === cls}
                title={CLASS_DESCRIPTION[cls]}
                onClick={() => onSelectClass(selectedClass === cls ? null : cls)}
              >
                <span className="rank-classes__label">{cls}</span>
                <span className="rank-classes__track">
                  <span
                    className="rank-classes__bar"
                    style={{ width: `${(count / max) * 100}%`, background: classColor(cls) }}
                  />
                </span>
                <span className="rank-classes__count">
                  {count.toLocaleString("en-US")}
                  <span className="rank-classes__pct"> · {total ? ((count / total) * 100).toFixed(1) : "0.0"}%</span>
                </span>
              </button>
            </li>
          );
        })}
      </ul>
      <p className="rank-card__hint">
        {selectedClass ? (
          <>
            <strong>{selectedClass}.</strong> {CLASS_DESCRIPTION[selectedClass]}{" "}
            <button type="button" className="rank-link" onClick={() => onSelectClass(null)}>
              Show all
            </button>
          </>
        ) : (
          "Click a class to highlight it in every chart on this page."
        )}
      </p>
    </div>
  );
}
