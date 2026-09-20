"""Parsers for the FungiDB-supplied RIB40 evidence files (Milestone 1).

These are input evidence for identifier reconciliation, not yet the frozen
canonical reference (PROJECT_MASTER_SPEC.md section 12); freezing the
reference is Milestone 3's job.
"""
from __future__ import annotations

import re
from pathlib import Path

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
