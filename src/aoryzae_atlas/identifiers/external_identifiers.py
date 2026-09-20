"""Build metadata/gene_external_identifiers.tsv rows (spec section 12).

Two sources feed this table:

1. The UniProt-workbook reconciliation (reconcile.MappingRow): one row each
   for the UniProtKB_accession, UniProtKB_entry_name, and any gene_alias
   tokens (from the "Aliases" field) tied to a confirmed AO09 gene. Rows
   whose mapping_type is "unmapped" are excluded here -- their AO09 id is
   not present in the FungiDB v71 gene set, so it cannot be recorded as a
   *canonical* gene id. That raw claim still lives in gene_id_mapping.tsv.

2. FungiDB-71_AoryzaeRIB40_GeneAliases.txt: only the "AO07"-prefixed
   alternate FungiDB gene id, under the "FungiDB" namespace. This file's
   real shape (fungidb.load_gene_aliases) is a variable-length, no-header
   TSV whose alias columns mix several id styles ("AO07...", "AO08...",
   "AOR_...", occasional other AO09 ids for merged/retired loci) plus a
   trailing AspGD "ASPL..." id. Only "AO07..." is documented and understood
   well enough to map to a namespace; PROJECT_MASTER_SPEC.md section 12's
   namespace list has no entry for the others, and guessing their semantics
   would risk exactly the kind of fabricated mapping AGENTS.md forbids. The
   full raw alias list is preserved in the row's evidence field regardless,
   so nothing is lost -- just not yet turned into a namespaced identifier.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from .ao09 import find_non_ao09_tokens
from .fungidb import load_gene_aliases
from .reconcile import MappingRow
from .uniprot_workbook import UniProtRow

_AO07_PATTERN = re.compile(r"AO07\d{10}")

_TSV_HEADER = [
    "canonical_gene_id",
    "namespace",
    "external_id",
    "external_name",
    "mapping_type",
    "mapping_confidence",
    "mapping_method",
    "evidence",
    "source_file",
    "source_version",
    "source_checksum",
    "reference_version",
]

# The exact UniProt query/reference-proteome/retrieval date behind the
# supplied workbook has not been confirmed (see database/FungiDB_v71/
# PROVENANCE.md); recording anything else here would be a guess.
_UNKNOWN_SOURCE_VERSION = "unknown (see database/FungiDB_v71/PROVENANCE.md)"


@dataclass(frozen=True)
class ExternalIdentifierRow:
    canonical_gene_id: str
    namespace: str
    external_id: str
    external_name: str
    mapping_type: str
    mapping_confidence: str
    mapping_method: str
    evidence: str
    source_file: str
    source_version: str
    source_checksum: str
    reference_version: str


def from_uniprot_mapping(
    mapping_rows: list[MappingRow],
    uniprot_rows: list[UniProtRow],
    source_file: str,
    source_checksum: str,
) -> list[ExternalIdentifierRow]:
    # A UniProt entry may legitimately appear on more than one row in this
    # workbook (see uniprot_workbook.explode_uniprot_gene_links); any one of
    # them carries the same Entry Name/Aliases, so the first is sufficient.
    row_by_entry: dict[str, UniProtRow] = {}
    for row in uniprot_rows:
        row_by_entry.setdefault(row.entry, row)

    rows: list[ExternalIdentifierRow] = []
    for mapping in mapping_rows:
        if mapping.mapping_type == "unmapped":
            continue
        source_row = row_by_entry.get(mapping.source_id)
        entry_name = source_row.entry_name if source_row else ""
        protein_name = (source_row.protein_names or "") if source_row else ""

        def _row(namespace: str, external_id: str, external_name: str, evidence: str) -> ExternalIdentifierRow:
            return ExternalIdentifierRow(
                canonical_gene_id=mapping.canonical_AO09_id,
                namespace=namespace,
                external_id=external_id,
                external_name=external_name,
                mapping_type=mapping.mapping_type,
                mapping_confidence=mapping.mapping_confidence,
                mapping_method=mapping.mapping_method,
                evidence=evidence,
                source_file=source_file,
                source_version=_UNKNOWN_SOURCE_VERSION,
                source_checksum=source_checksum,
                reference_version=mapping.reference_version,
            )

        rows.append(_row("UniProtKB_accession", mapping.source_id, protein_name, mapping.evidence))
        if entry_name:
            rows.append(_row("UniProtKB_entry_name", entry_name, protein_name, mapping.evidence))
        if source_row and source_row.aliases:
            for token in find_non_ao09_tokens(source_row.aliases):
                rows.append(_row("gene_alias", token, "", f"Aliases={source_row.aliases!r}"))
    return rows


def from_gene_aliases_file(
    gene_aliases_path: Path,
    fungidb_gene_ids: set[str],
    reference_version: str,
    source_file: str,
    source_checksum: str,
) -> list[ExternalIdentifierRow]:
    rows: list[ExternalIdentifierRow] = []
    for primary_id, alias_tokens in load_gene_aliases(gene_aliases_path):
        if primary_id not in fungidb_gene_ids:
            continue  # not an AO09 id in the confirmed gene set (e.g. a tRNA-gene row)
        evidence = "GeneAliases.txt row: " + "\t".join([primary_id, *alias_tokens])
        for token in alias_tokens:
            if not _AO07_PATTERN.fullmatch(token):
                continue  # AO08/AOR/other AO09/ASPL tokens: not yet mapped to a namespace, see module docstring
            rows.append(
                ExternalIdentifierRow(
                    canonical_gene_id=primary_id,
                    namespace="FungiDB",
                    external_id=token,
                    external_name="",
                    mapping_type="exact",
                    mapping_confidence="high",
                    mapping_method="fungidb_gene_aliases_file",
                    evidence=evidence,
                    source_file=source_file,
                    source_version=reference_version,
                    source_checksum=source_checksum,
                    reference_version=reference_version,
                )
            )
    return rows


def write_external_identifiers_tsv(rows: list[ExternalIdentifierRow], out_path: Path) -> None:
    with out_path.open("w", encoding="utf-8", newline="\n") as fh:
        fh.write("\t".join(_TSV_HEADER) + "\n")
        for row in rows:
            fh.write(
                "\t".join(
                    value.replace("\t", " ").replace("\n", " ")
                    for value in [
                        row.canonical_gene_id,
                        row.namespace,
                        row.external_id,
                        row.external_name,
                        row.mapping_type,
                        row.mapping_confidence,
                        row.mapping_method,
                        row.evidence,
                        row.source_file,
                        row.source_version,
                        row.source_checksum,
                        row.reference_version,
                    ]
                )
                + "\n"
            )
