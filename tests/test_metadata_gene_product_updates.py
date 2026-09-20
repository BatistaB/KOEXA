"""Tests for aoryzae_atlas.metadata.gene_product_updates (spec section 12)."""
from __future__ import annotations

from aoryzae_atlas.metadata.gene_product_updates import load_b71_products


def test_load_b71_products_skips_header_and_maps_gene_to_b71_product(tmp_path):
    path = tmp_path / "updates.txt"
    path.write_text(
        "gene_id\torganism\tb68_product\tb71_product\n"
        "AO090001000006\tAspergillus oryzae RIB40\tprotein of unknown function\t"
        "fungal STAND N-terminal Goodbye domain | domain-containing protein\n",
        encoding="utf-8",
    )
    updates = load_b71_products(path)
    assert updates == {
        "AO090001000006": "fungal STAND N-terminal Goodbye domain | domain-containing protein",
    }
