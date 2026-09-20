"""Parsers for the FungiDB-supplied RIB40 evidence files (Milestone 1).

These are input evidence for identifier reconciliation, not yet the frozen
canonical reference (PROJECT_MASTER_SPEC.md section 12); freezing the
reference is Milestone 3's job.
"""
from __future__ import annotations

import re
from pathlib import Path

from .ao09 import find_ao09_ids

_GENE_FIELD = re.compile(r"gene=(AO09\d{10})")


def load_protein_fasta_gene_ids(path: Path) -> list[str]:
    """Gene ids (with duplicates, in file order) from `gene=` FASTA header fields.

    One row per FASTA record (a gene may appear more than once if it has
    multiple annotated protein products); callers that need the distinct
    gene set should wrap the result in `set(...)`.
    """
    gene_ids: list[str] = []
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            if not line.startswith(">"):
                continue
            match = _GENE_FIELD.search(line)
            if match:
                gene_ids.append(match.group(1))
    return gene_ids


def load_gene_aliases(path: Path) -> list[tuple[str, list[str]]]:
    """Rows of (primary_id, alias_tokens).

    FungiDB-71_AoryzaeRIB40_GeneAliases.txt is a no-header TSV with a
    *variable* number of columns per line (verified across the full v71
    file: column counts from 2 to 9), not the fixed 3-column shape a small
    sample first suggested. Column 0 is a primary id -- usually an AO09
    protein-coding gene id, but tRNA gene rows use a different scheme (e.g.
    "AO090023t00008"). The remaining columns are a mix of alias types:
    "AO07"-prefixed alternate FungiDB gene ids, "AO08"-prefixed ids,
    "AOR_..." ids, occasional other AO09 ids (apparently merged/retired
    loci), and a trailing AspGD "ASPL..." id. Callers are responsible for
    filtering to the alias types they understand; this loader only splits
    the line.
    """
    rows: list[tuple[str, list[str]]] = []
    with path.open("r", encoding="utf-8") as fh:
        for raw_line in fh:
            line = raw_line.rstrip("\n")
            if not line:
                continue
            parts = line.split("\t")
            rows.append((parts[0], parts[1:]))
    return rows


def build_ao09_redirect_map(gene_aliases_path: Path, fungidb_gene_ids: set[str]) -> dict[str, str]:
    """Map a retired/renumbered AO09 id to the current gene it now aliases.

    Some `GeneAliases.txt` rows list an *additional* AO09-pattern token
    among a current gene's aliases (e.g. primary id AO090011000964 lists
    alias AO090011000551) -- evidence that AO090011000551 was merged or
    renumbered into AO090011000964 between annotation versions. Only
    aliases attached to a `primary_id` that is itself a confirmed current
    gene (in `fungidb_gene_ids`) are trusted; every old id observed this
    way in the v71 release resolves to exactly one current gene (verified
    2026-09-20 by exhaustive check), so this returns a 1:1 mapping rather
    than a multi-target one -- if a future release ever produces more than
    one target for the same old id, that id is dropped here rather than
    guessed.
    """
    redirect_map: dict[str, set[str]] = {}
    for primary_id, alias_tokens in load_gene_aliases(gene_aliases_path):
        if primary_id not in fungidb_gene_ids:
            continue
        for token in alias_tokens:
            for old_id in find_ao09_ids(token):
                if old_id != primary_id:
                    redirect_map.setdefault(old_id, set()).add(primary_id)
    return {old_id: next(iter(targets)) for old_id, targets in redirect_map.items() if len(targets) == 1}
