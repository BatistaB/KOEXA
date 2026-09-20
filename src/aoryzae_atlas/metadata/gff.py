"""Minimal GFF3 reader scoped to the FungiDB v71 RIB40 protein-coding genes.

Only the `protein_coding_gene` feature type is read (12,090 features in the
v71 release, matching the protein/CDS FASTA record counts exactly -- see
reports/gene_id_mapping_summary.txt). The file also carries mRNA/exon/CDS/
UTR features and non-coding genes (ncRNA_gene, tRNA, rRNA); those describe
structure below the gene level or a different biotype and are out of scope
for the gene_master.tsv table this module feeds.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from urllib.parse import unquote

_PROTEIN_CODING_GENE = "protein_coding_gene"


@dataclass(frozen=True)
class GffGene:
    gene_id: str
    chromosome: str
    start: int
    end: int
    strand: str
    description: str | None
    biotype: str


def _parse_attributes(attr_field: str) -> dict[str, str]:
    attrs: dict[str, str] = {}
    for part in attr_field.split(";"):
        key, sep, value = part.partition("=")
        if sep:
            attrs[key] = unquote(value)
    return attrs


def load_protein_coding_genes(gff_path: Path) -> list[GffGene]:
    genes: list[GffGene] = []
    with gff_path.open("r", encoding="utf-8") as fh:
        for line in fh:
            if line.startswith("#") or not line.strip():
                continue
            fields = line.rstrip("\n").split("\t")
            if len(fields) != 9 or fields[2] != _PROTEIN_CODING_GENE:
                continue
            seqid, _source, _type, start, end, _score, strand, _phase, attr_field = fields
            attrs = _parse_attributes(attr_field)
            gene_id = attrs.get("ID")
            if not gene_id:
                continue
            genes.append(
                GffGene(
                    gene_id=gene_id,
                    chromosome=seqid,
                    start=int(start),
                    end=int(end),
                    strand=strand,
                    description=attrs.get("description"),
                    biotype=attrs.get("ebi_biotype", "protein_coding"),
                )
            )
    return genes
