"""Tests for aoryzae_atlas.identifiers.uniprot_workbook (spec section 12)."""
from __future__ import annotations

from aoryzae_atlas.identifiers.uniprot_workbook import UniProtRow, explode_uniprot_gene_links


def test_explode_single_gene_from_genes_field():
    row = UniProtRow(
        entry="A0A0H5BJN0",
        entry_name="A0A0H5BJN0_ASPOR",
        protein_names="AsorizinA",
        aliases="oeiA",
        genes_field="AO090103000076",
        row_number=1,
    )
    links = explode_uniprot_gene_links([row])
    assert len(links) == 1
    assert links[0].ao09_id == "AO090103000076"
    assert links[0].source_field == "Genes"


def test_explode_finds_extra_locus_only_in_aliases():
    # Real shape from the supplied workbook: Genes has one locus, Aliases
    # carries a second, slash-separated locus for a fused/tandem ORF pair.
    row = UniProtRow(
        entry="A7BJS7",
        entry_name="PRTT_ASPOR",
        protein_names="Transcriptional activator of proteases prtT",
        aliases="prtT prtR AO090003001211/AO090003001212",
        genes_field="AO090003001211",
        row_number=2,
    )
    links = explode_uniprot_gene_links([row])
    ao09_ids = {link.ao09_id: link.source_field for link in links}
    assert ao09_ids == {
        "AO090003001211": "Genes",
        "AO090003001212": "Aliases",
    }


def test_explode_dedupes_across_pre_exploded_duplicate_rows():
    # Real shape seen in the supplied workbook for entry "Q2TX49": the same
    # entry appears on three rows, each with a different single AO09 id in
    # Genes, but the SAME three-id Aliases string repeated on every row.
    # Without grouping by entry first, this would double-count each link
    # (once from its own Genes hit, again from every row's Aliases hit).
    aliases_text = "AO090010000290 AO090010000292 AO090038000137"
    rows = [
        UniProtRow("Q2TX49", "Q2TX49_ASPOR", None, aliases_text, "AO090010000290", 1),
        UniProtRow("Q2TX49", "Q2TX49_ASPOR", None, aliases_text, "AO090010000292", 2),
        UniProtRow("Q2TX49", "Q2TX49_ASPOR", None, aliases_text, "AO090038000137", 3),
    ]
    links = explode_uniprot_gene_links(rows)
    ao09_ids = [link.ao09_id for link in links]
    assert sorted(ao09_ids) == ["AO090010000290", "AO090010000292", "AO090038000137"]
    assert len(ao09_ids) == len(set(ao09_ids))  # no duplicate (entry, ao09_id) pairs


def test_explode_no_ids_produces_no_links():
    row = UniProtRow(
        entry="X",
        entry_name="X_ASPOR",
        protein_names=None,
        aliases=None,
        genes_field=None,
        row_number=1,
    )
    assert explode_uniprot_gene_links([row]) == []
