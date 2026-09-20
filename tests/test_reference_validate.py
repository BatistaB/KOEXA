"""Tests for aoryzae_atlas.reference.validate (spec section 37 Milestone 3)."""
from __future__ import annotations

from aoryzae_atlas.reference.validate import validate_reference

GENOME_FASTA = ">Chr1\nACGTACGTAC\nGTACGTACGT\n>Chr2\nACGTA\n>Chr3\nACGTA\n>Chr4\nACGTA\n>Chr5\nACGTA\n"
GENOME_FASTA += ">Chr6\nACGTA\n>Chr7\nACGTA\n>Chr8\nACGTA\n>c1\nAC\n>c2\nAC\n>c3\nAC\n>mito\nACGTA\n"

GFF = (
    "##gff-version 3\n"
    "Chr1\tVEuPathDB\tprotein_coding_gene\t1\t20\t.\t+\t.\tID=AO090001000001;description=x;ebi_biotype=protein_coding\n"
    "Chr1\tVEuPathDB\tprotein_coding_gene\t30\t50\t.\t-\t.\tID=AO090001000002;description=y;ebi_biotype=protein_coding\n"
)

PROTEIN_FASTA = ">AO090001000001-T-p1 | gene=AO090001000001\nMK\n>AO090001000002-T-p1 | gene=AO090001000002\nMK\n"

TRANSCRIPT_FASTA = ">AO090001000001-T | gene=AO090001000001\nACGT\n>AO090001000002-T | gene=AO090001000002\nACGT\n"


def _write(tmp_path, name, content):
    path = tmp_path / name
    path.write_text(content, encoding="utf-8")
    return path


def test_validate_reference_all_consistent(tmp_path):
    genome = _write(tmp_path, "genome.fasta", GENOME_FASTA)
    gff = _write(tmp_path, "annot.gff", GFF)
    protein = _write(tmp_path, "protein.fasta", PROTEIN_FASTA)
    transcript = _write(tmp_path, "transcript.fasta", TRANSCRIPT_FASTA)

    report = validate_reference(genome, gff, protein, transcript)
    assert report.genome_sequence_count == 12
    assert report.gff_gene_count == 2
    assert report.protein_fasta_gene_count == 2
    assert report.genes_match_gff_and_protein_fasta is True
    assert report.t2g_genes_are_subset_of_gff is True
    assert report.problems == []
    assert set(report.checksums) == {"genome_fasta_sha256", "annotation_sha256", "transcript_fasta_sha256"}


def test_validate_reference_flags_gene_set_mismatch(tmp_path):
    genome = _write(tmp_path, "genome.fasta", GENOME_FASTA)
    gff = _write(tmp_path, "annot.gff", GFF)
    # Protein FASTA is missing one of the GFF's two genes.
    protein = _write(tmp_path, "protein.fasta", ">AO090001000001-T-p1 | gene=AO090001000001\nMK\n")
    transcript = _write(tmp_path, "transcript.fasta", TRANSCRIPT_FASTA)

    report = validate_reference(genome, gff, protein, transcript)
    assert report.genes_match_gff_and_protein_fasta is False
    assert any("differ" in p for p in report.problems)


def test_validate_reference_flags_unexpected_sequence_count(tmp_path):
    genome = _write(tmp_path, "genome.fasta", ">Chr1\nACGT\n")  # only 1 sequence, not 12
    gff = _write(tmp_path, "annot.gff", GFF)
    protein = _write(tmp_path, "protein.fasta", PROTEIN_FASTA)
    transcript = _write(tmp_path, "transcript.fasta", TRANSCRIPT_FASTA)

    report = validate_reference(genome, gff, protein, transcript)
    assert any("12 genome sequences" in p for p in report.problems)
