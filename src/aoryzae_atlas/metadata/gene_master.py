"""Build metadata/gene_master.tsv (spec section 12's "genes" table).

`gene_symbol` and `gene_name` are left blank for every row here, on
purpose: the only symbol-like evidence available is the UniProt workbook's
"Aliases" field, which routinely lists more than one token per gene (e.g.
"prtT prtR" for AO090003001211) with no way to tell which, if any, is the
*primary* symbol. That full alias set is already recorded, without picking
a winner, as gene_alias rows in gene_external_identifiers.tsv
(identifiers.external_identifiers). Silently promoting one alias to
gene_master.tsv's gene_symbol/gene_name here would be exactly the kind of
guess AGENTS.md forbids; it is left for an explicit future curation step.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .gff import GffGene

_TSV_HEADER = [
    "canonical_gene_id",
    "gene_symbol",
    "gene_name",
    "chromosome",
    "start",
    "end",
    "strand",
    "biotype",
    "description",
    "reference_version",
]


@dataclass(frozen=True)
class GeneMasterRow:
    canonical_gene_id: str
    gene_symbol: str
    gene_name: str
    chromosome: str
    start: int
    end: int
    strand: str
    biotype: str
    description: str
    reference_version: str


def build_gene_master_rows(
    genes: list[GffGene],
    b71_products: dict[str, str],
    reference_version: str,
) -> list[GeneMasterRow]:
    rows: list[GeneMasterRow] = []
    for gene in genes:
        description = b71_products.get(gene.gene_id) or gene.description or ""
        rows.append(
            GeneMasterRow(
                canonical_gene_id=gene.gene_id,
                gene_symbol="",
                gene_name="",
                chromosome=gene.chromosome,
                start=gene.start,
                end=gene.end,
                strand=gene.strand,
                biotype=gene.biotype,
                description=description,
                reference_version=reference_version,
            )
        )
    return rows


def write_gene_master_tsv(rows: list[GeneMasterRow], out_path: Path) -> None:
    with out_path.open("w", encoding="utf-8", newline="\n") as fh:
        fh.write("\t".join(_TSV_HEADER) + "\n")
        for row in rows:
            values = [
                row.canonical_gene_id,
                row.gene_symbol,
                row.gene_name,
                row.chromosome,
                str(row.start),
                str(row.end),
                row.strand,
                row.biotype,
                row.description,
                row.reference_version,
            ]
            fh.write("\t".join(v.replace("\t", " ").replace("\n", " ") for v in values) + "\n")
