"""Shared sample-tag vocabulary (metadata/sample_tag_vocabulary.tsv).

Tags are independent, reusable sample attributes (`glucose`, `submerged`,
`wild_type`, ...) shared by every study, so that a later cross-study
analysis can ask "all samples tagged hypoxia" without knowing how each
paper phrased it. Two kinds of tag are valid:

* **Vocabulary tags** -- one row each in the TSV, with a category, a
  definition and the synonyms it absorbs. A synonym is never itself a
  valid tag: writing `liquid_culture` is an error that names `submerged`
  as the tag to use, which is how redundant near-duplicates are kept out.
* **Parametric tags** -- open families whose value is part of the tag
  (`30C`, `24h`, `3h_post_treatment`, `ph_5_5`, `strain_rib40`,
  `del_faaA`, `oe_cutL1`). They need no TSV row; their regex is the
  definition.

Before adding a new vocabulary row, check `suggest()` for an existing tag
or synonym that already means the same thing (see
.claude/skills/annotate-study/SKILL.md).
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path

import pandas as pd

__all__ = [
    "PARAMETRIC_FAMILIES",
    "TagVocabulary",
    "VocabularyError",
    "load_vocabulary",
]

VOCAB_TAG_RE = re.compile(r"^[a-z][a-z0-9_]*$")

# (category, regex, description) -- order matters only for reporting.
PARAMETRIC_FAMILIES: list[tuple[str, re.Pattern[str], str]] = [
    ("temperature", re.compile(r"^\d+(\.\d+)?C$"), "Cultivation temperature in degrees Celsius, e.g. 30C."),
    ("time", re.compile(r"^\d+(\.\d+)?h_post_treatment$"),
     "Hours since the treatment/shift started (or the matched time in a parallel control), e.g. 3h_post_treatment."),
    ("time", re.compile(r"^\d+(\.\d+)?h$"), "Culture age in hours since inoculation/incubation start (days x 24), e.g. 72h."),
    ("pH", re.compile(r"^ph_\d+(_\d+)?$"), "Medium pH, decimal point written as '_', e.g. ph_5_5."),
    ("strain", re.compile(r"^strain_[a-z0-9_]+$"), "Strain or genetic background, lower-case, punctuation as '_', e.g. strain_rib40."),
    ("genotype", re.compile(r"^del_[A-Za-z][A-Za-z0-9]*$"), "Named gene deleted/disrupted, gene symbol as published, e.g. del_faaA."),
    ("genotype", re.compile(r"^oe_[A-Za-z][A-Za-z0-9]*$"), "Named gene overexpressed, gene symbol as published, e.g. oe_cutL1."),
]


class VocabularyError(ValueError):
    """Raised when the vocabulary TSV itself is inconsistent."""


@dataclass(frozen=True)
class VocabularyEntry:
    tag: str
    category: str
    description: str
    synonyms: tuple[str, ...]


class TagVocabulary:
    def __init__(self, entries: list[VocabularyEntry]):
        self.entries = {e.tag: e for e in entries}
        self.synonym_to_tag: dict[str, str] = {}
        for entry in entries:
            for synonym in entry.synonyms:
                if synonym in self.entries:
                    raise VocabularyError(f"synonym '{synonym}' of '{entry.tag}' is itself a vocabulary tag")
                other = self.synonym_to_tag.get(synonym)
                if other is not None and other != entry.tag:
                    raise VocabularyError(f"synonym '{synonym}' is claimed by both '{other}' and '{entry.tag}'")
                self.synonym_to_tag[synonym] = entry.tag

    def category(self, tag: str) -> str | None:
        """Category of a valid tag, or None if the tag is not valid."""
        if tag in self.entries:
            return self.entries[tag].category
        for category, pattern, _ in PARAMETRIC_FAMILIES:
            if pattern.match(tag):
                return category
        return None

    def check(self, tag: str) -> str | None:
        """None if `tag` is valid; otherwise a one-line reason (with a fix when one is known)."""
        if self.category(tag) is not None:
            return None
        canonical = self.synonym_to_tag.get(tag) or self.synonym_to_tag.get(tag.lower())
        if canonical:
            return f"'{tag}' is a synonym of the existing tag '{canonical}'; use '{canonical}'"
        hints = self.suggest(tag)
        hint = f" (similar existing tags: {', '.join(hints)})" if hints else ""
        return f"'{tag}' is not in metadata/sample_tag_vocabulary.tsv and matches no parametric family{hint}"

    def suggest(self, text: str, limit: int = 5, cutoff: float = 0.6) -> list[str]:
        """Existing tags whose name or a synonym resembles `text` -- check before adding a new tag."""
        needle = re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")
        scored: dict[str, float] = {}
        for tag, entry in self.entries.items():
            for name in (tag, *entry.synonyms):
                score = SequenceMatcher(None, needle, name).ratio()
                if needle and (needle in name or name in needle):
                    score = max(score, 0.8)
                if score >= cutoff:
                    scored[tag] = max(scored.get(tag, 0.0), score)
        return [tag for tag, _ in sorted(scored.items(), key=lambda kv: -kv[1])[:limit]]


def load_vocabulary(path: Path) -> TagVocabulary:
    frame = pd.read_csv(path, sep="\t", dtype=str, keep_default_na=False)
    missing = {"tag", "category", "description", "synonyms"} - set(frame.columns)
    if missing:
        raise VocabularyError(f"{path} is missing column(s): {', '.join(sorted(missing))}")
    entries: list[VocabularyEntry] = []
    seen: set[str] = set()
    for row in frame.itertuples(index=False):
        tag = row.tag.strip()
        if not VOCAB_TAG_RE.match(tag):
            raise VocabularyError(f"vocabulary tag '{tag}' must be lower-case snake_case")
        if tag in seen:
            raise VocabularyError(f"vocabulary tag '{tag}' is listed twice")
        if any(pattern.match(tag) for _, pattern, _ in PARAMETRIC_FAMILIES):
            raise VocabularyError(f"vocabulary tag '{tag}' collides with a parametric family; drop the row")
        if not row.category.strip() or not row.description.strip():
            raise VocabularyError(f"vocabulary tag '{tag}' needs a category and a description")
        seen.add(tag)
        synonyms = tuple(s.strip() for s in row.synonyms.split(";") if s.strip())
        entries.append(VocabularyEntry(tag, row.category.strip(), row.description.strip(), synonyms))
    return TagVocabulary(entries)
