"""Curated study annotations: metadata/study_annotations/<BIOPROJECT>.json.

One hand-reviewed JSON file per study holds (a) the associated paper,
(b) a 2-4 sentence objective / experimental design / main finding
summary, and (c) per-sample tags drawn from the shared vocabulary
(vocabulary.py). The files are the source of truth; the database tables
and the web export are derived from them (same policy as
metadata/conditions.tsv).

Tags are assigned per curated condition (every replicate run of a
condition shares its tags) through reusable `tag_sets`, plus optional
per-run extras in `sample_tags`. Each tag carries where it came from and
how sure we are -- the provenance stays in the database even though the UI
only shows the tag name:

    {"tag": "glucose", "source": "paper_methods", "confidence": "high"}

A paper association is never guessed: `paper.status` is `not_found` (or
`ambiguous`) unless an accession-level link (NCBI elink, or the paper's
data-availability statement naming the BioProject/SRA/GEO accession)
supports it.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pandas as pd

from .vocabulary import TagVocabulary

__all__ = [
    "PAPER_STATUSES",
    "TAG_CONFIDENCES",
    "TAG_SOURCES",
    "ResolvedTag",
    "StudyAnnotation",
    "load_annotation",
    "load_all_annotations",
    "validate_annotation",
]

SCHEMA_VERSION = 1
PAPER_STATUSES = {"found", "not_found", "ambiguous"}
PAPER_ACCESS = {"full_text", "abstract_only", "metadata_only", "none"}
TAG_SOURCES = {
    "sample_metadata",          # SRA/BioSample attributes, sample titles
    "bioproject_description",   # BioProject/SRA study title or abstract
    "curated_condition",        # metadata/conditions.tsv (itself sourced)
    "paper_methods",            # stated in the paper's Methods
    "paper_abstract",           # stated in the abstract/results
    "inferred_from_methods",    # follows from the Methods but is not stated verbatim
    "inferred_from_design",     # follows from the experimental design/naming
}
TAG_CONFIDENCES = {"high", "medium", "low"}
SUMMARY_FIELDS = ("objective", "experimental_design", "main_finding")


@dataclass(frozen=True)
class ResolvedTag:
    tag: str
    category: str
    source: str
    confidence: str
    note: str


@dataclass
class StudyAnnotation:
    path: Path
    raw: dict[str, Any]
    bioproject: str = field(init=False)

    def __post_init__(self) -> None:
        self.bioproject = str(self.raw.get("bioproject", ""))

    @property
    def paper(self) -> dict[str, Any]:
        return self.raw.get("paper") or {}

    @property
    def summary(self) -> dict[str, str]:
        return self.raw.get("study_summary") or {}

    def tags_for(self, sample_id: str, condition_id: str | None, vocabulary: TagVocabulary) -> list[ResolvedTag]:
        """Union of the condition's tag sets/tags and the run's own extras; first occurrence wins."""
        entries: list[dict[str, Any]] = []
        condition = (self.raw.get("conditions") or {}).get(condition_id or "", {})
        for set_name in condition.get("sets", []):
            entries.extend(self.raw.get("tag_sets", {}).get(set_name, []))
        entries.extend(condition.get("tags", []))
        entries.extend((self.raw.get("sample_tags") or {}).get(sample_id, []))
        resolved: dict[str, ResolvedTag] = {}
        for entry in entries:
            tag = entry["tag"]
            if tag not in resolved:
                resolved[tag] = ResolvedTag(
                    tag=tag,
                    category=vocabulary.category(tag) or "unknown",
                    source=entry.get("source", ""),
                    confidence=entry.get("confidence", ""),
                    note=entry.get("note", ""),
                )
        return list(resolved.values())


def load_annotation(path: Path) -> StudyAnnotation:
    return StudyAnnotation(path=path, raw=json.loads(path.read_text(encoding="utf-8")))


def load_all_annotations(directory: Path) -> list[StudyAnnotation]:
    if not directory.is_dir():
        return []
    return [load_annotation(p) for p in sorted(directory.glob("*.json"))]


def _check_tag_entry(entry: Any, where: str, vocabulary: TagVocabulary, problems: list[str]) -> None:
    if not isinstance(entry, dict) or "tag" not in entry:
        problems.append(f"{where}: tag entries must be objects with at least a 'tag' key")
        return
    reason = vocabulary.check(entry["tag"])
    if reason:
        problems.append(f"{where}: {reason}")
    if entry.get("source") not in TAG_SOURCES:
        problems.append(f"{where}: tag '{entry['tag']}' has source {entry.get('source')!r}; expected one of {sorted(TAG_SOURCES)}")
    if entry.get("confidence") not in TAG_CONFIDENCES:
        problems.append(f"{where}: tag '{entry['tag']}' has confidence {entry.get('confidence')!r}; expected high/medium/low")


def validate_annotation(
    annotation: StudyAnnotation, vocabulary: TagVocabulary, samples: pd.DataFrame
) -> list[str]:
    """All problems found (empty list = valid). `samples` is metadata/samples.tsv as strings."""
    raw, problems = annotation.raw, []
    where = annotation.path.name
    if raw.get("schema_version") != SCHEMA_VERSION:
        problems.append(f"{where}: schema_version must be {SCHEMA_VERSION}")
    if annotation.path.stem != annotation.bioproject:
        problems.append(f"{where}: file name must match bioproject '{annotation.bioproject}'")

    paper = annotation.paper
    status = paper.get("status")
    if status not in PAPER_STATUSES:
        problems.append(f"{where}: paper.status must be one of {sorted(PAPER_STATUSES)}")
    if status == "found":
        for key in ("title", "year", "association_evidence"):
            if not paper.get(key):
                problems.append(f"{where}: paper.status is 'found' but paper.{key} is empty")
        if not (paper.get("doi") or paper.get("pmid") or paper.get("url")):
            problems.append(f"{where}: a found paper needs at least one of doi/pmid/url")
        if paper.get("access") not in PAPER_ACCESS:
            problems.append(f"{where}: paper.access must be one of {sorted(PAPER_ACCESS)}")

    summary = annotation.summary
    for key in SUMMARY_FIELDS:
        text = (summary.get(key) or "").strip()
        if not text:
            problems.append(f"{where}: study_summary.{key} is empty")
        elif len(text) > 600:
            problems.append(f"{where}: study_summary.{key} is {len(text)} chars; keep it to 1-2 short sentences")

    tag_sets = raw.get("tag_sets") or {}
    for set_name, entries in tag_sets.items():
        for entry in entries:
            _check_tag_entry(entry, f"{where} tag_sets.{set_name}", vocabulary, problems)
    conditions = raw.get("conditions") or {}
    for condition_id, spec in conditions.items():
        for set_name in spec.get("sets", []):
            if set_name not in tag_sets:
                problems.append(f"{where} conditions.{condition_id}: unknown tag set '{set_name}'")
        for entry in spec.get("tags", []):
            _check_tag_entry(entry, f"{where} conditions.{condition_id}", vocabulary, problems)
    for sample_id, entries in (raw.get("sample_tags") or {}).items():
        for entry in entries:
            _check_tag_entry(entry, f"{where} sample_tags.{sample_id}", vocabulary, problems)

    study_samples = samples[samples["bioproject"] == annotation.bioproject]
    known_conditions = set(study_samples["condition_id"]) - {""}
    for condition_id in sorted(set(conditions) - known_conditions):
        problems.append(f"{where}: condition '{condition_id}' has no sample in metadata/samples.tsv for this study")
    for sample_id in sorted(set(raw.get("sample_tags") or {}) - set(study_samples["sample_id"])):
        problems.append(f"{where}: sample_tags references unknown sample '{sample_id}'")
    for row in study_samples.itertuples(index=False):
        if not annotation.tags_for(row.sample_id, row.condition_id, vocabulary):
            problems.append(f"{where}: sample {row.sample_id} (condition '{row.condition_id}') resolves to no tags")
    return problems
