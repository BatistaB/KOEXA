"""Loader for FungiDB-71_AoryzaeRIB40_gene_product_updates_b71.txt.

A small (563-row), header-having, fixed 4-column TSV: gene_id, organism,
b68_product, b71_product. Only b71_product (the current release's product
description) is used; it takes priority over the GFF's own `description`
attribute when both exist for a gene, since it is FungiDB's more recent
annotation update for that specific gene.
"""
from __future__ import annotations

from pathlib import Path


def load_b71_products(path: Path) -> dict[str, str]:
    updates: dict[str, str] = {}
    with path.open("r", encoding="utf-8") as fh:
        next(fh, None)  # header: gene_id, organism, b68_product, b71_product
        for line in fh:
            parts = line.rstrip("\n").split("\t")
            if len(parts) != 4:
                continue
            gene_id, _organism, _b68_product, b71_product = parts
            if b71_product:
                updates[gene_id] = b71_product
    return updates
