"""Tests for aoryzae_atlas.identifiers.fungidb (spec section 12)."""
from __future__ import annotations

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


def test_load_gene_aliases_variable_column_counts(tmp_path):
    # The real file has 2 to 9 columns per row: a 2-column tRNA-gene row,
    # a normal 3-column row, and a 4-column row with an extra alias id.
    aliases_path = tmp_path / "aliases.txt"
    aliases_path.write_text(
        "AO090023t00008\ttI(AAT)3\n"
        "AO090023000525\tAO070280000026\tASPL0000279297\n"
        "AO090011000743\tAO070340000164\tAO080523000711\tASPL0000280980\n",
        encoding="utf-8",
    )
    rows = load_gene_aliases(aliases_path)
    assert rows == [
        ("AO090023t00008", ["tI(AAT)3"]),
        ("AO090023000525", ["AO070280000026", "ASPL0000279297"]),
        ("AO090011000743", ["AO070340000164", "AO080523000711", "ASPL0000280980"]),
    ]
