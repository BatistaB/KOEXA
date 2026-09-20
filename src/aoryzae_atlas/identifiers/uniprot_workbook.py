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
    """
    links: list[UniProtGeneLink] = []
    for row in rows:
        first_hit_field: dict[str, str] = {}
        for field_name, field_value in (("Genes", row.genes_field), ("Aliases", row.aliases)):
            for ao09_id in find_ao09_ids(field_value):
                first_hit_field.setdefault(ao09_id, field_name)
        for ao09_id, field_name in first_hit_field.items():
            evidence_value = row.genes_field if field_name == "Genes" else row.aliases
            links.append(
                UniProtGeneLink(
                    uniprot_entry=row.entry,
                    uniprot_entry_name=row.entry_name,
                    ao09_id=ao09_id,
                    source_field=field_name,
                    evidence=f"{field_name}={evidence_value!r}",
                )
            )
    return links
