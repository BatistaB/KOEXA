"""Tests for aoryzae_atlas.reference.genome_fasta (spec section 37 Milestone 3)."""
from __future__ import annotations

from aoryzae_atlas.reference.genome_fasta import load_genome_sequence_lengths

FASTA_SAMPLE = """\
>Chr1_A_oryzae_RIB40 | organism=Aspergillus_oryzae_RIB40 | version=2015-10-04 | length=20
ACGTACGTAC
GTACGTACGT
>mito_A_oryzae_RIB40 | organism=Aspergillus_oryzae_RIB40 | version=2015-10-04 | length=5
ACGTA
"""


def test_counts_actual_bases_not_the_header_length_field(tmp_path):
    path = tmp_path / "genome.fasta"
    path.write_text(FASTA_SAMPLE, encoding="utf-8")
    sequences = load_genome_sequence_lengths(path)
    assert len(sequences) == 2
    assert sequences[0].name == "Chr1_A_oryzae_RIB40"
    assert sequences[0].length == 20
    assert sequences[1].name == "mito_A_oryzae_RIB40"
    assert sequences[1].length == 5
