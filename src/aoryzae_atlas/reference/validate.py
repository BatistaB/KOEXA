"""Structural validation for the Milestone 3 canonical-reference evidence.

Cross-checks the genome FASTA, GFF3 annotation, and transcript FASTA
against each other and against Milestone 1's already-validated protein
FASTA gene set, and computes the checksums config/reference.yaml records.
Does not build a Salmon index (Milestone 5, via nf-core/rnaseq) and does
not flip `frozen: true` on its own -- that is a separate, explicit step
requiring human sign-off (PROJECT_MASTER_SPEC.md section 37 Milestone 3:
"stop and report if AO09/reference assumptions remain unclear").
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

from ..identifiers.fungidb import load_protein_fasta_gene_ids
from ..metadata.gff import load_protein_coding_genes
from .genome_fasta import load_genome_sequence_lengths
from .transcript_to_gene import load_transcript_to_gene


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


@dataclass(frozen=True)
class ReferenceValidationReport:
    genome_sequence_count: int
    genome_total_length: int
    gff_gene_count: int
    protein_fasta_gene_count: int
    transcript_fasta_record_count: int
    t2g_pair_count: int
    t2g_gene_count: int
    genes_match_gff_and_protein_fasta: bool
    t2g_genes_are_subset_of_gff: bool
    problems: list[str]
    checksums: dict[str, str]


def validate_reference(
    genome_fasta_path: Path,
    gff_path: Path,
    protein_fasta_path: Path,
    transcript_fasta_path: Path,
) -> ReferenceValidationReport:
    genome_sequences = load_genome_sequence_lengths(genome_fasta_path)
    gff_genes = load_protein_coding_genes(gff_path)
    gff_gene_ids = {g.gene_id for g in gff_genes}
    protein_gene_ids = set(load_protein_fasta_gene_ids(protein_fasta_path))
    t2g_pairs = load_transcript_to_gene(transcript_fasta_path)
    t2g_gene_ids = {gene_id for _transcript_id, gene_id in t2g_pairs}

    problems: list[str] = []
    genes_match = gff_gene_ids == protein_gene_ids
    if not genes_match:
        only_gff = gff_gene_ids - protein_gene_ids
        only_protein = protein_gene_ids - gff_gene_ids
        problems.append(
            f"GFF and protein FASTA gene sets differ: {len(only_gff)} only in GFF, "
            f"{len(only_protein)} only in protein FASTA"
        )

    t2g_subset = t2g_gene_ids <= gff_gene_ids
    if not t2g_subset:
        problems.append(f"{len(t2g_gene_ids - gff_gene_ids)} transcript-to-gene genes are absent from the GFF")

    if len(genome_sequences) != 12:
        problems.append(f"expected 12 genome sequences (8 chr + 3 contig + mito), found {len(genome_sequences)}")

    checksums = {
        "genome_fasta_sha256": sha256_file(genome_fasta_path),
        "annotation_sha256": sha256_file(gff_path),
        "transcript_fasta_sha256": sha256_file(transcript_fasta_path),
    }

    return ReferenceValidationReport(
        genome_sequence_count=len(genome_sequences),
        genome_total_length=sum(s.length for s in genome_sequences),
        gff_gene_count=len(gff_gene_ids),
        protein_fasta_gene_count=len(protein_gene_ids),
        transcript_fasta_record_count=len(t2g_pairs),
        t2g_pair_count=len(t2g_pairs),
        t2g_gene_count=len(t2g_gene_ids),
        genes_match_gff_and_protein_fasta=genes_match,
        t2g_genes_are_subset_of_gff=t2g_subset,
        problems=problems,
        checksums=checksums,
    )


def render_validation_report(report: ReferenceValidationReport) -> str:
    lines = [
        "AOED Milestone 3 -- canonical RIB40 reference structural validation",
        "",
        f"Genome: {report.genome_sequence_count} sequences, {report.genome_total_length:,} bp total",
        f"GFF protein-coding genes: {report.gff_gene_count}",
        f"Protein FASTA genes: {report.protein_fasta_gene_count}",
        f"GFF/protein FASTA gene sets match exactly: {report.genes_match_gff_and_protein_fasta}",
        f"Transcript FASTA records: {report.transcript_fasta_record_count}",
        f"Transcript-to-gene pairs: {report.t2g_pair_count} ({report.t2g_gene_count} distinct genes)",
        f"All t2g genes present in GFF: {report.t2g_genes_are_subset_of_gff}",
        "",
        "Checksums (SHA256):",
    ]
    for name, value in report.checksums.items():
        lines.append(f"  {name}: {value}")
    lines += ["", "Problems found:" if report.problems else "No problems found."]
    lines += [f"  - {p}" for p in report.problems]
    return "\n".join(lines) + "\n"
