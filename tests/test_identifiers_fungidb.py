"""Tests for aoryzae_atlas.identifiers.fungidb (spec section 12)."""
from __future__ import annotations

import pytest

from aoryzae_atlas.identifiers.fungidb import load_gene_aliases, load_protein_fasta_gene_ids

FASTA_SAMPLE = """\
>AO090005000001-T-p1 | transcript=AO090005000001-T | gene=AO090005000001 | organism=Aspergillus_oryzae_RIB40
MLISSVAKDGYGKDIWTLPFDSITRILKFTWLLQLLYIPALAATKMAFLCLYLRIFPSTG
>AO090005000002-T-p1 | transcript=AO090005000002-T | gene=AO090005000002 | organism=Aspergillus_oryzae_RIB40
MDLLRLRDRSLLGQGALVAFVTYWAVWIIYTRWFHPLAKFPGPFWASVTRAWTLLHVLHG
"""


def test_load_protein_fasta_gene_ids(tmp_path):
    fasta_path = tmp_path / "proteins.fasta"
    fasta_path.write_text(FASTA_SAMPLE, encoding="utf-8")
    assert load_protein_fasta_gene_ids(fasta_path) == ["AO090005000001", "AO090005000002"]


def test_load_gene_aliases(tmp_path):
    aliases_path = tmp_path / "aliases.txt"
    aliases_path.write_text(
        "AO090023000525\tAO070280000026\tASPL0000279297\n"
        "AO090009000020\tAO070342000441\tASPL0000279299\n",
        encoding="utf-8",
    )
    rows = load_gene_aliases(aliases_path)
    assert rows == [
        ("AO090023000525", "AO070280000026", "ASPL0000279297"),
        ("AO090009000020", "AO070342000441", "ASPL0000279299"),
    ]


def test_load_gene_aliases_rejects_malformed_row(tmp_path):
    aliases_path = tmp_path / "aliases.txt"
    aliases_path.write_text("AO090023000525\tAO070280000026\n", encoding="utf-8")
    with pytest.raises(ValueError):
        load_gene_aliases(aliases_path)
