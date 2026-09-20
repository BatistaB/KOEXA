"""AO09 <-> UniProt reconciliation (Milestone 1, spec section 12).

Compares the AO09 gene ids referenced by the user-supplied UniProt-derived
workbook against the AO09 gene set actually present in the FungiDB v71
RIB40 protein FASTA. Both are input evidence, not yet a frozen reference;
Milestone 3 freezes the canonical reference and re-verifies against this
milestone's findings.

Classification (pure functions) is kept separate from file I/O so it can be
tested without real workbook/FASTA files.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from pathlib import Path

from .fungidb import load_protein_fasta_gene_ids
from .uniprot_workbook import UniProtGeneLink, UniProtRow, explode_uniprot_gene_links, load_uniprot_workbook

# Every AO09 id originates from the RIB40 genome annotation by construction
# (that is what the AO09 namespace *is*), so recording "RIB40" as the source
# strain for any row keyed by a real AO09 id is a structural fact, not a
# guess -- it does not claim anything about the UniProt entry's own strain
# provenance beyond that.
_SOURCE_STRAIN = "RIB40"
_SOURCE_NAMESPACE = "UniProtKB_accession"


@dataclass(frozen=True)
class MappingRow:
    source_id: str
    source_namespace: str
    source_strain: str
    canonical_AO09_id: str
    mapping_type: str
    mapping_confidence: str
    mapping_method: str
    evidence: str
    reference_version: str


def classify_links(
    links: list[UniProtGeneLink],
    fungidb_gene_ids: set[str],
    reference_version: str,
) -> list[MappingRow]:
    genes_per_entry: dict[str, set[str]] = {}
    entries_per_gene: dict[str, set[str]] = {}
    for link in links:
        genes_per_entry.setdefault(link.uniprot_entry, set()).add(link.ao09_id)
        entries_per_gene.setdefault(link.ao09_id, set()).add(link.uniprot_entry)

    rows: list[MappingRow] = []
    for link in links:
        in_fungidb = link.ao09_id in fungidb_gene_ids
        n_genes = len(genes_per_entry[link.uniprot_entry])
        n_entries = len(entries_per_gene[link.ao09_id])

        if not in_fungidb:
            mapping_type, confidence = "unmapped", "low"
        elif n_genes == 1 and n_entries == 1:
            mapping_type, confidence = "exact", "high"
        elif n_genes > 1 and n_entries == 1:
            mapping_type, confidence = "one_to_many", "medium"
        elif n_genes == 1 and n_entries > 1:
            mapping_type, confidence = "many_to_one", "medium"
        else:
            mapping_type, confidence = "ambiguous", "low"

        rows.append(
            MappingRow(
                source_id=link.uniprot_entry,
                source_namespace=_SOURCE_NAMESPACE,
                source_strain=_SOURCE_STRAIN,
                canonical_AO09_id=link.ao09_id,
                mapping_type=mapping_type,
                mapping_confidence=confidence,
                mapping_method=f"uniprot_workbook_{link.source_field.lower()}_field",
                evidence=link.evidence,
                reference_version=reference_version,
            )
        )
    return rows


@dataclass(frozen=True)
class ReconciliationSummary:
    n_uniprot_rows: int
    n_uniprot_entries: int
    n_gene_links: int
    n_fungidb_genes: int
    mapping_type_counts: dict[str, int]
    fungidb_genes_without_uniprot: list[str]
    duplicate_uniprot_entries: list[str]


def summarize(
    mapping_rows: list[MappingRow],
    uniprot_rows: list[UniProtRow],
    fungidb_gene_ids: set[str],
) -> ReconciliationSummary:
    mapped_genes = {r.canonical_AO09_id for r in mapping_rows if r.mapping_type != "unmapped"}
    entry_counts = Counter(r.entry for r in uniprot_rows)
    return ReconciliationSummary(
        n_uniprot_rows=len(uniprot_rows),
        n_uniprot_entries=len(entry_counts),
        n_gene_links=len(mapping_rows),
        n_fungidb_genes=len(fungidb_gene_ids),
        mapping_type_counts=dict(Counter(r.mapping_type for r in mapping_rows)),
        fungidb_genes_without_uniprot=sorted(fungidb_gene_ids - mapped_genes),
        duplicate_uniprot_entries=sorted(entry for entry, count in entry_counts.items() if count > 1),
    )


@dataclass(frozen=True)
class ReconciliationResult:
    mapping_rows: list[MappingRow]
    summary: ReconciliationSummary
    uniprot_rows: list[UniProtRow]
    fungidb_gene_ids: set[str]


def run_reconciliation(workbook_path: Path, protein_fasta_path: Path, reference_version: str) -> ReconciliationResult:
    uniprot_rows = load_uniprot_workbook(workbook_path)
    links = explode_uniprot_gene_links(uniprot_rows)
    fungidb_gene_ids = set(load_protein_fasta_gene_ids(protein_fasta_path))
    mapping_rows = classify_links(links, fungidb_gene_ids, reference_version)
    summary = summarize(mapping_rows, uniprot_rows, fungidb_gene_ids)
    return ReconciliationResult(
        mapping_rows=mapping_rows,
        summary=summary,
        uniprot_rows=uniprot_rows,
        fungidb_gene_ids=fungidb_gene_ids,
    )


_MAPPING_TSV_HEADER = [
    "source_id",
    "source_namespace",
    "source_strain",
    "canonical_AO09_id",
    "mapping_type",
    "mapping_confidence",
    "mapping_method",
    "evidence",
    "reference_version",
]


def write_mapping_tsv(mapping_rows: list[MappingRow], out_path: Path) -> None:
    with out_path.open("w", encoding="utf-8", newline="\n") as fh:
        fh.write("\t".join(_MAPPING_TSV_HEADER) + "\n")
        for row in mapping_rows:
            fh.write(
                "\t".join(
                    [
                        row.source_id,
                        row.source_namespace,
                        row.source_strain,
                        row.canonical_AO09_id,
                        row.mapping_type,
                        row.mapping_confidence,
                        row.mapping_method,
                        row.evidence.replace("\t", " ").replace("\n", " "),
                        row.reference_version,
                    ]
                )
                + "\n"
            )


def render_summary_report(summary: ReconciliationSummary, reference_version: str) -> str:
    lines = [
        "AOED Milestone 1 -- AO09/UniProt reconciliation report",
        f"Reference version (evidence, not frozen): {reference_version}",
        "",
        f"UniProt workbook rows:        {summary.n_uniprot_rows}",
        f"Distinct UniProt entries:     {summary.n_uniprot_entries}",
        f"UniProt-entry/AO09 links:     {summary.n_gene_links}",
        f"FungiDB v71 RIB40 gene set:   {summary.n_fungidb_genes}",
        "",
        "Mapping type counts:",
    ]
    for mapping_type, count in sorted(summary.mapping_type_counts.items()):
        lines.append(f"  {mapping_type:<12} {count}")
    lines += [
        "",
        f"Duplicate UniProt entries in workbook: {len(summary.duplicate_uniprot_entries)}",
    ]
    lines += [f"  {entry}" for entry in summary.duplicate_uniprot_entries[:50]]
    if len(summary.duplicate_uniprot_entries) > 50:
        lines.append(f"  ... and {len(summary.duplicate_uniprot_entries) - 50} more")
    lines += [
        "",
        f"FungiDB v71 genes with no UniProt workbook coverage: {len(summary.fungidb_genes_without_uniprot)}",
        "(full list follows; these are 'missing' per spec section 37 Milestone 1, not an error)",
    ]
    lines += [f"  {gene_id}" for gene_id in summary.fungidb_genes_without_uniprot]
    return "\n".join(lines) + "\n"
