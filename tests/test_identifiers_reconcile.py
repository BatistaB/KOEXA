"""Tests for aoryzae_atlas.identifiers.reconcile (spec section 12)."""
from __future__ import annotations

from aoryzae_atlas.identifiers.uniprot_workbook import UniProtGeneLink, UniProtRow
from aoryzae_atlas.identifiers.reconcile import classify_links, summarize


def _link(entry: str, ao09_id: str, field: str = "Genes") -> UniProtGeneLink:
    return UniProtGeneLink(
        uniprot_entry=entry,
        uniprot_entry_name=f"{entry}_ASPOR",
        ao09_id=ao09_id,
        source_field=field,
        evidence=f"{field}={ao09_id!r}",
    )


def test_exact_mapping():
    links = [_link("P1", "AO090001000001")]
    rows = classify_links(links, {"AO090001000001"}, "FungiDB_v71")
    assert len(rows) == 1
    assert rows[0].mapping_type == "exact"
    assert rows[0].mapping_confidence == "high"
    assert rows[0].source_strain == "RIB40"
    assert rows[0].reference_version == "FungiDB_v71"


def test_unmapped_when_gene_not_in_fungidb_set():
    links = [_link("P1", "AO090001000099")]
    rows = classify_links(links, {"AO090001000001"}, "FungiDB_v71")
    assert rows[0].mapping_type == "unmapped"


def test_one_to_many_one_entry_two_genes():
    links = [_link("P1", "AO090001000001"), _link("P1", "AO090001000002", field="Aliases")]
    rows = classify_links(links, {"AO090001000001", "AO090001000002"}, "FungiDB_v71")
    assert {r.mapping_type for r in rows} == {"one_to_many"}


def test_many_to_one_two_entries_one_gene():
    links = [_link("P1", "AO090001000001"), _link("P2", "AO090001000001")]
    rows = classify_links(links, {"AO090001000001"}, "FungiDB_v71")
    assert {r.mapping_type for r in rows} == {"many_to_one"}


def test_classification_is_per_pair_not_per_entry_or_per_gene():
    # P1 fans out to two genes (AO...01, AO...02); AO...01 itself has two
    # entries (P1, P2). Each (entry, gene) pair is classified by its own
    # cardinality on both sides, so the three pairs get three different
    # mapping_types even though they share an entry or a gene:
    #  - P1/AO...01: both sides fan out            -> ambiguous
    #  - P1/AO...02: only the entry side fans out   -> one_to_many
    #  - P2/AO...01: only the gene side fans out    -> many_to_one
    links = [
        _link("P1", "AO090001000001"),
        _link("P1", "AO090001000002"),
        _link("P2", "AO090001000001"),
    ]
    rows = classify_links(links, {"AO090001000001", "AO090001000002"}, "FungiDB_v71")
    types = {r.source_id + r.canonical_AO09_id: r.mapping_type for r in rows}
    assert types["P1AO090001000001"] == "ambiguous"
    assert types["P1AO090001000002"] == "one_to_many"
    assert types["P2AO090001000001"] == "many_to_one"


def test_summarize_counts_and_missing_genes():
    links = [_link("P1", "AO090001000001")]
    fungidb_genes = {"AO090001000001", "AO090001000002"}
    rows = classify_links(links, fungidb_genes, "FungiDB_v71")
    uniprot_rows = [
        UniProtRow("P1", "P1_ASPOR", None, None, "AO090001000001", 1),
        UniProtRow("P1", "P1_ASPOR", None, None, "AO090001000001", 2),  # duplicate entry
    ]
    summary = summarize(rows, uniprot_rows, fungidb_genes)
    assert summary.n_uniprot_rows == 2
    assert summary.n_uniprot_entries == 1
    assert summary.duplicate_uniprot_entries == ["P1"]
    assert summary.fungidb_genes_without_uniprot == ["AO090001000002"]
    assert summary.mapping_type_counts == {"exact": 1}
