import { useMemo, useState } from "react";
import type { StudyAnnotation } from "../../data/types";
import "./StudyAnnotationView.css";

/** Chip tint per vocabulary category family (metadata/sample_tag_vocabulary.tsv). */
const CATEGORY_TONE: Record<string, string> = {
  role: "role",
  genotype: "genotype",
  strain: "genotype",
  biological_material: "biology",
  growth_phase: "biology",
  culture_system: "culture",
  medium: "culture",
  carbon_source: "culture",
  nitrogen_source: "culture",
  substrate: "culture",
  compound: "perturbation",
  stress: "perturbation",
  oxygen: "perturbation",
  industrial_context: "culture",
};

export function TagChip({ tag, category }: { tag: string; category: string | undefined }) {
  const tone = (category && CATEGORY_TONE[category]) ?? "neutral";
  return (
    <span className={`tag-chip tag-chip--${tone}`} title={category ? category.replace(/_/g, " ") : undefined}>
      {tag}
    </span>
  );
}

function paperLine(paper: StudyAnnotation["paper"]): string {
  return [paper.authors, paper.journal, paper.year].filter(Boolean).join(" · ");
}

interface StudyAnnotationViewProps {
  annotation: StudyAnnotation;
  tagCategories: Record<string, string>;
}

export function StudyAnnotationView({ annotation, tagCategories }: StudyAnnotationViewProps) {
  const { paper, summary, samples } = annotation;
  const [compact, setCompact] = useState(false);

  // Tags every run shares are shown once; in compact mode each run then
  // lists only what distinguishes it within the study.
  const sharedTags = useMemo(() => {
    if (samples.length === 0) return [];
    return samples[0].tags.filter((tag) => samples.every((s) => s.tags.includes(tag)));
  }, [samples]);
  const shared = useMemo(() => new Set(sharedTags), [sharedTags]);

  return (
    <>
      <div className="right-panel__section">
        {paper.status === "found" ? (
          <p className="study-annotation__title">{paper.title}</p>
        ) : (
          <p className="right-panel__prose">
            {paper.status === "ambiguous"
              ? "Associated paper ambiguous — not assigned."
              : "No associated paper found (paper_status: not_found)."}
          </p>
        )}
        <div className="study-annotation__field">
          <div className="study-annotation__field-label">Objective</div>
          <p className="right-panel__prose">{summary.objective}</p>
        </div>
        <div className="study-annotation__field">
          <div className="study-annotation__field-label">Experimental design</div>
          <p className="right-panel__prose">{summary.experimental_design}</p>
        </div>
        <div className="study-annotation__field">
          <div className="study-annotation__field-label">Main finding</div>
          <p className="right-panel__prose">{summary.main_finding}</p>
        </div>
      </div>

      {paper.status === "found" && (
        <div className="right-panel__section">
          <div className="right-panel__section-label">Paper</div>
          {paperLine(paper) && <p className="study-annotation__byline">{paperLine(paper)}</p>}
          {paper.url && (
            <a className="study-annotation__link" href={paper.url} target="_blank" rel="noreferrer">
              {paper.doi ? `doi:${paper.doi}` : paper.url} ↗
            </a>
          )}
          {paper.pmid && (
            <a
              className="study-annotation__link study-annotation__link--secondary"
              href={`https://pubmed.ncbi.nlm.nih.gov/${paper.pmid}/`}
              target="_blank"
              rel="noreferrer"
            >
              PMID {paper.pmid} ↗
            </a>
          )}
        </div>
      )}

      <div className="right-panel__section">
        <div className="study-annotation__samples-head">
          <div className="right-panel__section-label">Samples &amp; tags</div>
          <button type="button" className="study-annotation__toggle" onClick={() => setCompact((c) => !c)}>
            {compact ? "Show all tags" : "Show differences only"}
          </button>
        </div>
        {compact && sharedTags.length > 0 && (
          <div className="study-annotation__shared">
            <div className="study-annotation__field-label">All {samples.length} runs</div>
            <div className="study-annotation__chips">
              {sharedTags.map((tag) => (
                <TagChip key={tag} tag={tag} category={tagCategories[tag]} />
              ))}
            </div>
          </div>
        )}
        <ul className="study-annotation__runs">
          {samples.map((s) => {
            const tags = compact ? s.tags.filter((tag) => !shared.has(tag)) : s.tags;
            return (
              <li key={s.sample_id} className="study-annotation__run">
                <span className="study-annotation__run-id mono" title={s.condition_id}>
                  {s.sample_id}
                </span>
                <div className="study-annotation__chips">
                  {tags.length > 0 ? (
                    tags.map((tag) => <TagChip key={tag} tag={tag} category={tagCategories[tag]} />)
                  ) : (
                    <span className="study-annotation__none">no distinguishing tags</span>
                  )}
                </div>
              </li>
            );
          })}
        </ul>
      </div>
    </>
  );
}
