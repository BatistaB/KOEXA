"""Shared AO09 canonical gene identifier pattern (spec section 12).

AO09 identifiers are the RIB40 gene-model identifiers from the 2005
A. oryzae genome annotation: the literal prefix "AO09" followed by 10
digits (e.g. AO090001000001). FungiDB's GeneAliases.txt also carries an
"AO07"-prefixed identifier of the same length for the same genes -- that is
a different, non-canonical namespace and must never be matched by this
pattern.
"""
from __future__ import annotations

import re

AO09_PATTERN = re.compile(r"AO09\d{10}")


def find_ao09_ids(text: str | None) -> list[str]:
    """Return AO09 ids found anywhere in `text`, de-duplicated, first-seen order."""
    if not text:
        return []
    seen: dict[str, None] = {}
    for match in AO09_PATTERN.findall(text):
        seen.setdefault(match, None)
    return list(seen)


def find_non_ao09_tokens(text: str | None) -> list[str]:
    """Return whitespace/slash-separated tokens in `text` that are not AO09 ids.

    Used to pull gene symbols/synonyms (e.g. "prtT", "prtR") out of a UniProt
    "Aliases" field that also contains AO09 loci.
    """
    if not text:
        return []
    tokens: list[str] = []
    for chunk in text.replace("/", " ").split():
        if not AO09_PATTERN.fullmatch(chunk):
            tokens.append(chunk)
    return tokens
