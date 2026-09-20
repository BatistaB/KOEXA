"""Tests for aoryzae_atlas.reference.transcript_to_gene (spec section 37 Milestone 3)."""
from __future__ import annotations

from aoryzae_atlas.reference.transcript_to_gene import load_transcript_to_gene, write_t2g_tsv

FASTA_SAMPLE = """\
>AO090005000001-T | gene=AO090005000001 | organism=Aspergillus_oryzae_RIB40 | length=888
ACGT
>AO090005000002-T | gene=AO090005000002 | organism=Aspergillus_oryzae_RIB40 | length=1527
ACGT
"""


def test_load_transcript_to_gene(tmp_path):
    path = tmp_path / "transcripts.fasta"
    path.write_text(FASTA_SAMPLE, encoding="utf-8")
    pairs = load_transcript_to_gene(path)
    assert pairs == [
        ("AO090005000001-T", "AO090005000001"),
        ("AO090005000002-T", "AO090005000002"),
    ]


def test_write_t2g_tsv(tmp_path):
    out_path = tmp_path / "t2g.tsv"
    write_t2g_tsv([("AO090005000001-T", "AO090005000001")], out_path)
    assert out_path.read_text(encoding="utf-8") == "transcript_id\tgene_id\nAO090005000001-T\tAO090005000001\n"
