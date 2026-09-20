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
