"""Loader for the user-supplied UniProt-derived workbook (Milestone 1).

Only the identifier-relevant columns are read. The source workbook was
reused from an unrelated metabolic-model spreadsheet and also carries
columns such as "Model Function"/"Translation Reaction"; those are ignored
here and must not be treated as AOED data.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from .ao09 import find_ao09_ids

_COLUMNS = ["Entry", "Entry Name", "Protein names", "Aliases", "Genes"]


@dataclass(frozen=True)
class UniProtRow:
    entry: str
    entry_name: str
    protein_names: str | None
    aliases: str | None
    genes_field: str | None
    row_number: int  # 1-based data row (Excel row 2 == row_number 1), for evidence/debugging


def load_uniprot_workbook(path: Path, sheet_name: str = "Sheet1") -> list[UniProtRow]:
    frame = pd.read_excel(path, sheet_name=sheet_name, usecols=_COLUMNS, dtype=str)
    rows: list[UniProtRow] = []
    for i, record in frame.iterrows():
        entry = record["Entry"]
        if pd.isna(entry) or not str(entry).strip():
            continue
        rows.append(
            UniProtRow(
                entry=str(entry).strip(),
                entry_name=str(record["Entry Name"]).strip() if pd.notna(record["Entry Name"]) else "",
                protein_names=str(record["Protein names"]) if pd.notna(record["Protein names"]) else None,
                aliases=str(record["Aliases"]) if pd.notna(record["Aliases"]) else None,
                genes_field=str(record["Genes"]) if pd.notna(record["Genes"]) else None,
                row_number=int(i) + 1,
            )
        )
    return rows


@dataclass(frozen=True)
class UniProtGeneLink:
    uniprot_entry: str
    uniprot_entry_name: str
    ao09_id: str
    source_field: str  # "Genes" or "Aliases"
    evidence: str


def explode_uniprot_gene_links(rows: list[UniProtRow]) -> list[UniProtGeneLink]:
    """One link per (UniProt entry, AO09 id) pair found in Genes or Aliases.

    UniProt's "Genes" (primary/ordered-locus name) field holds one locus per
    entry in this workbook; entries covering more than one RIB40 locus
    (fused/tandem ORFs sharing one protein entry) carry the extra locus only
    in "Aliases" -- e.g. Genes="AO090003001211" but
    Aliases="prtT prtR AO090003001211/AO090003001212". Both fields are
    scanned and unioned (Genes preferred when an id appears in both) so a
    real one-to-many relationship (PROJECT_MASTER_SPEC.md section 12) is
    never missed.

    The same UniProt entry can appear on more than one row: this workbook's
    own upstream processing sometimes pre-explodes a multi-gene entry into
    one row per gene while repeating the *full* Aliases text on every one of
    those rows (e.g. three rows for entry "Q2TX49", each with a different
    single AO09 id in Genes but the same three-id Aliases string on all
    three). Rows are grouped by entry before scanning so that case produces
    exactly one link per distinct AO09 id, not one per duplicate row.
    """
    rows_by_entry: dict[str, list[UniProtRow]] = {}
    for row in rows:
        rows_by_entry.setdefault(row.entry, []).append(row)

    links: list[UniProtGeneLink] = []
    for entry, entry_rows in rows_by_entry.items():
        entry_name = entry_rows[0].entry_name
        first_hit: dict[str, tuple[str, str | None]] = {}  # ao09_id -> (field_name, field_value)
        for row in entry_rows:
            for field_name, field_value in (("Genes", row.genes_field), ("Aliases", row.aliases)):
                for ao09_id in find_ao09_ids(field_value):
                    first_hit.setdefault(ao09_id, (field_name, field_value))
        for ao09_id, (field_name, field_value) in first_hit.items():
            links.append(
                UniProtGeneLink(
                    uniprot_entry=entry,
                    uniprot_entry_name=entry_name,
                    ao09_id=ao09_id,
                    source_field=field_name,
                    evidence=f"{field_name}={field_value!r}",
                )
            )
    return links
