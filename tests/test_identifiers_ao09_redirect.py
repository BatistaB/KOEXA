"""Tests for the GeneAliases.txt AO09 redirect resolution (spec section 12).

Real-data finding (2026-09-20): every one of the 566 AO09 ids the UniProt
workbook references but that are absent from the FungiDB v71 gene set
resolves, via GeneAliases.txt, to exactly one current gene -- evidence the
workbook was built against an older/renumbered AO09 catalog. 274 of the 562
FungiDB v71 genes with no direct UniProt coverage turn out to have indirect
coverage this way.
"""
from __future__ import annotations

from pathlib import Path

from aoryzae_atlas.identifiers.fungidb import build_ao09_redirect_map
from aoryzae_atlas.identifiers.reconcile import apply_ao09_redirects, classify_links
from aoryzae_atlas.identifiers.uniprot_workbook import UniProtGeneLink


def _link(ao09_id: str) -> UniProtGeneLink:
    return UniProtGeneLink(
        uniprot_entry="P1",
        uniprot_entry_name="P1_ASPOR",
        ao09_id=ao09_id,
        source_field="Genes",
        evidence=f"Genes={ao09_id!r}",
    )


def test_build_ao09_redirect_map_only_trusts_current_gene_primaries(tmp_path):
    aliases_path = tmp_path / "aliases.txt"
    aliases_path.write_text(
        # primary is a current gene: its extra AO09 alias becomes a trusted redirect.
        "AO090011000964\tAO070340000355\tAO090011000551\tASPL0000367822\n"
        # primary is NOT a current gene: nothing here should be trusted.
        "AO090099999999\tAO090011000552\n",
        encoding="utf-8",
    )
    redirect_map = build_ao09_redirect_map(aliases_path, fungidb_gene_ids={"AO090011000964"})
    assert redirect_map == {"AO090011000551": "AO090011000964"}


def test_apply_ao09_redirects_only_touches_ids_missing_from_fungidb():
    links = [_link("AO090011000551"), _link("AO090011000964")]
    fungidb_gene_ids = {"AO090011000964"}
    redirect_map = {"AO090011000551": "AO090011000964"}
    resolved = apply_ao09_redirects(links, fungidb_gene_ids, redirect_map)

    redirected = next(l for l in resolved if l.redirected_from == "AO090011000551")
    assert redirected.ao09_id == "AO090011000964"
    direct = next(l for l in resolved if l.redirected_from is None)
    assert direct.ao09_id == "AO090011000964"


def test_apply_ao09_redirects_leaves_unresolvable_ids_alone():
    links = [_link("AO090099999999")]
    resolved = apply_ao09_redirects(links, fungidb_gene_ids=set(), redirect_map={})
    assert resolved == links


def test_redirected_link_classifies_as_annotation_alias_not_exact():
    links = apply_ao09_redirects(
        [_link("AO090011000551")],
        fungidb_gene_ids={"AO090011000964"},
        redirect_map={"AO090011000551": "AO090011000964"},
    )
    rows = classify_links(links, fungidb_gene_ids={"AO090011000964"}, reference_version="FungiDB_v71")
    assert len(rows) == 1
    assert rows[0].mapping_type == "annotation_alias"
    assert rows[0].mapping_confidence == "medium"
    assert rows[0].canonical_AO09_id == "AO090011000964"
    assert rows[0].mapping_method == "fungidb_gene_aliases_redirect"
    assert "redirected AO090011000551 -> AO090011000964" in rows[0].evidence
