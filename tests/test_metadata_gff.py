"""Tests for aoryzae_atlas.metadata.gff (spec section 12)."""
from __future__ import annotations

from aoryzae_atlas.metadata.gff import load_protein_coding_genes

GFF_SAMPLE = """\
##gff-version 3
##sequence-region Chr2_A_oryzae_RIB40 1 6264705
Chr2_A_oryzae_RIB40\tVEuPathDB\tprotein_coding_gene\t350\t1289\t.\t+\t.\tID=AO090001000001;description=Ortholog(s) have role in austinol biosynthetic process%2C dehydroaustinol biosynthetic process;ebi_biotype=protein_coding
Chr2_A_oryzae_RIB40\tVEuPathDB\tmRNA\t350\t1289\t.\t+\t.\tID=AO090001000001-T1;Parent=AO090001000001
Chr2_A_oryzae_RIB40\tVEuPathDB\tncRNA_gene\t2000\t2200\t.\t+\t.\tID=AO090001000002;ebi_biotype=ncRNA
"""


def test_load_protein_coding_genes_only_returns_that_feature_type(tmp_path):
    gff_path = tmp_path / "sample.gff"
    gff_path.write_text(GFF_SAMPLE, encoding="utf-8")
    genes = load_protein_coding_genes(gff_path)
    assert len(genes) == 1
    gene = genes[0]
    assert gene.gene_id == "AO090001000001"
    assert gene.chromosome == "Chr2_A_oryzae_RIB40"
    assert gene.start == 350
    assert gene.end == 1289
    assert gene.strand == "+"
    assert gene.biotype == "protein_coding"


def test_load_protein_coding_genes_url_decodes_description(tmp_path):
    gff_path = tmp_path / "sample.gff"
    gff_path.write_text(GFF_SAMPLE, encoding="utf-8")
    gene = load_protein_coding_genes(gff_path)[0]
    assert gene.description == (
        "Ortholog(s) have role in austinol biosynthetic process, dehydroaustinol biosynthetic process"
    )
