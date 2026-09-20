"""Tests for aoryzae_atlas.metadata.gene_master (spec section 12)."""
from __future__ import annotations

from aoryzae_atlas.metadata.gene_master import build_gene_master_rows
from aoryzae_atlas.metadata.gff import GffGene


def test_b71_product_overrides_gff_description_when_present():
    genes = [
        GffGene("AO090001000001", "Chr1", 350, 1289, "+", "GFF description", "protein_coding"),
        GffGene("AO090001000002", "Chr1", 2000, 3000, "-", "Only GFF description here", "protein_coding"),
    ]
    b71_products = {"AO090001000001": "Updated b71 product"}
    rows = build_gene_master_rows(genes, b71_products, "FungiDB_v71")

    by_id = {r.canonical_gene_id: r for r in rows}
    assert by_id["AO090001000001"].description == "Updated b71 product"
    assert by_id["AO090001000002"].description == "Only GFF description here"


def test_gene_symbol_and_gene_name_are_left_blank():
    genes = [GffGene("AO090001000001", "Chr1", 350, 1289, "+", "desc", "protein_coding")]
    rows = build_gene_master_rows(genes, {}, "FungiDB_v71")
    assert rows[0].gene_symbol == ""
    assert rows[0].gene_name == ""


def test_missing_description_becomes_empty_string_not_none():
    genes = [GffGene("AO090001000001", "Chr1", 350, 1289, "+", None, "protein_coding")]
    rows = build_gene_master_rows(genes, {}, "FungiDB_v71")
    assert rows[0].description == ""
