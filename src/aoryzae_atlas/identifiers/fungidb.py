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


def load_gene_aliases(path: Path) -> list[tuple[str, str, str]]:
    """Rows of (canonical_AO09_id, fungidb_alt_gene_id, aspgd_locus_id).

    FungiDB-71_AoryzaeRIB40_GeneAliases.txt is a fixed 3-column TSV with no
    header (verified by manual inspection of the v71 release): the AO09
    canonical id, an "AO07"-prefixed alternate FungiDB gene id, and an
    AspGD "ASPL..." literature/locus id.
    """
    rows: list[tuple[str, str, str]] = []
    with path.open("r", encoding="utf-8") as fh:
        for line_no, raw_line in enumerate(fh, start=1):
            line = raw_line.rstrip("\n")
            if not line:
                continue
            parts = line.split("\t")
            if len(parts) != 3:
                raise ValueError(f"{path}:{line_no}: expected 3 tab-separated fields, got {len(parts)}")
            rows.append((parts[0], parts[1], parts[2]))
    return rows
