"""Load the curated study annotations into DuckDB (migration 0002).

Fully derived from metadata/study_annotations/*.json and
metadata/sample_tag_vocabulary.tsv: truncate and reload, never merge.
Every annotation is validated first; an invalid file aborts the whole load
rather than loading a partial vocabulary.
"""
from __future__ import annotations

import json
from pathlib import Path

import duckdb
import pandas as pd

from .schema import load_all_annotations, validate_annotation
from .vocabulary import load_vocabulary

__all__ = ["AnnotationValidationError", "load_study_annotations"]


class AnnotationValidationError(Exception):
    def __init__(self, problems: list[str]):
        super().__init__(f"{len(problems)} annotation problem(s):\n  " + "\n  ".join(problems))
        self.problems = problems


def load_study_annotations(
    conn: duckdb.DuckDBPyConnection,
    annotations_dir: Path,
    vocabulary_tsv: Path,
    samples_tsv: Path,
) -> tuple[int, int]:
    """Returns (n_studies, n_sample_tag_rows)."""
    vocabulary = load_vocabulary(vocabulary_tsv)
    samples = pd.read_csv(samples_tsv, sep="\t", dtype=str, keep_default_na=False)
    annotations = load_all_annotations(annotations_dir)
    problems = [p for a in annotations for p in validate_annotation(a, vocabulary, samples)]
    if problems:
        raise AnnotationValidationError(problems)

    study_rows, tag_rows = [], []
    for annotation in annotations:
        paper, summary, raw = annotation.paper, annotation.summary, annotation.raw
        curation = raw.get("curation") or {}
        study_rows.append({
            "bioproject": annotation.bioproject,
            "paper_status": paper.get("status"),
            "paper_title": paper.get("title"),
            "paper_authors": paper.get("authors"),
            "paper_year": paper.get("year"),
            "paper_journal": paper.get("journal"),
            "paper_doi": paper.get("doi"),
            "paper_pmid": paper.get("pmid"),
            "paper_pmcid": paper.get("pmcid"),
            "paper_url": paper.get("url"),
            "paper_access": paper.get("access"),
            "association_evidence": paper.get("association_evidence"),
            "objective": summary.get("objective"),
            "experimental_design": summary.get("experimental_design"),
            "main_finding": summary.get("main_finding"),
            "related_identifiers": json.dumps(raw.get("related_identifiers") or {}),
            "notes": json.dumps(raw.get("notes") or []),
            "curated_by": curation.get("curated_by"),
            "curated_at": curation.get("curated_at"),
            "source_file": annotation.path.name,
        })
        study_samples = samples[samples["bioproject"] == annotation.bioproject]
        for row in study_samples.itertuples(index=False):
            for tag in annotation.tags_for(row.sample_id, row.condition_id, vocabulary):
                tag_rows.append({
                    "sample_id": row.sample_id, "bioproject": annotation.bioproject, "tag": tag.tag,
                    "category": tag.category, "source": tag.source, "confidence": tag.confidence, "note": tag.note,
                })

    vocab_rows = [
        {"tag": e.tag, "category": e.category, "description": e.description, "synonyms": ";".join(e.synonyms)}
        for e in vocabulary.entries.values()
    ]
    for table, rows in (("tag_vocabulary", vocab_rows), ("study_annotations", study_rows), ("sample_tags", tag_rows)):
        conn.execute(f"DELETE FROM {table}")
        if rows:
            frame = pd.DataFrame(rows)
            if table == "study_annotations":
                frame["paper_year"] = pd.to_numeric(frame["paper_year"], errors="coerce").astype("Int64")
            conn.register("frame", frame)
            conn.execute(f"INSERT INTO {table} ({', '.join(frame.columns)}) SELECT * FROM frame")
            conn.unregister("frame")
    return len(study_rows), len(tag_rows)
