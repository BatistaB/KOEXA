"""Tests for aoryzae_atlas.identifiers.external_identifiers (spec section 12)."""
from __future__ import annotations

from aoryzae_atlas.identifiers.external_identifiers import from_gene_aliases_file, from_uniprot_mapping
from aoryzae_atlas.identifiers.reconcile import MappingRow
from aoryzae_atlas.identifiers.uniprot_workbook import UniProtRow


def _mapping_row(source_id: str, ao09_id: str, mapping_type: str = "exact") -> MappingRow:
    return MappingRow(
        source_id=source_id,
        source_namespace="UniProtKB_accession",
        source_strain="RIB40",
        canonical_AO09_id=ao09_id,
        mapping_type=mapping_type,
        mapping_confidence="high" if mapping_type == "exact" else "low",
        mapping_method="uniprot_workbook_genes_field",
        evidence=f"Genes={ao09_id!r}",
        reference_version="FungiDB_v71",
    )


def test_from_uniprot_mapping_emits_accession_entry_name_and_alias_rows():
    mapping_rows = [_mapping_row("A7BJS7", "AO090003001211")]
    uniprot_rows = [
        UniProtRow(
            entry="A7BJS7",
            entry_name="PRTT_ASPOR",
            protein_names="Transcriptional activator of proteases prtT",
            aliases="prtT prtR AO090003001211/AO090003001212",
            genes_field="AO090003001211",
            row_number=1,
        )
    ]
    rows = from_uniprot_mapping(mapping_rows, uniprot_rows, source_file="workbook.xlsx", source_checksum="deadbeef")
    by_namespace = {(r.namespace, r.external_id) for r in rows}
    assert ("UniProtKB_accession", "A7BJS7") in by_namespace
    assert ("UniProtKB_entry_name", "PRTT_ASPOR") in by_namespace
    assert ("gene_alias", "prtT") in by_namespace
    assert ("gene_alias", "prtR") in by_namespace
    # The two AO09 tokens in Aliases must not leak in as gene_alias entries.
    assert not any(r.namespace == "gene_alias" and r.external_id.startswith("AO09") for r in rows)
    assert all(r.canonical_gene_id == "AO090003001211" for r in rows)


def test_from_uniprot_mapping_excludes_unmapped_rows():
    mapping_rows = [_mapping_row("P1", "AO090001000099", mapping_type="unmapped")]
    uniprot_rows = [UniProtRow("P1", "P1_ASPOR", None, None, "AO090001000099", 1)]
    rows = from_uniprot_mapping(mapping_rows, uniprot_rows, source_file="workbook.xlsx", source_checksum="deadbeef")
    assert rows == []


def test_from_gene_aliases_file_only_includes_confirmed_genes(tmp_path):
    aliases_path = tmp_path / "aliases.txt"
    aliases_path.write_text(
        "AO090023000525\tAO070280000026\tASPL0000279297\n"
        "AO090009000020\tAO070342000441\tASPL0000279299\n",
        encoding="utf-8",
    )
    rows = from_gene_aliases_file(
        aliases_path,
        fungidb_gene_ids={"AO090023000525"},  # the second row's gene is NOT in this set
        reference_version="FungiDB_v71",
        source_file="aliases.txt",
        source_checksum="cafef00d",
    )
    assert len(rows) == 1
    assert rows[0].canonical_gene_id == "AO090023000525"
    assert rows[0].namespace == "FungiDB"
    assert rows[0].external_id == "AO070280000026"
    assert rows[0].mapping_type == "exact"


def test_from_gene_aliases_file_skips_unrecognized_alias_types_and_non_ao09_rows(tmp_path):
    aliases_path = tmp_path / "aliases.txt"
    aliases_path.write_text(
        # tRNA-gene row (primary id is not a plain AO09 id): must not crash
        # and must not appear (it also won't be in fungidb_gene_ids).
        "AO090023t00008\ttI(AAT)3\n"
        # AO08-prefixed and ASPL tokens are not yet mapped to a namespace;
        # only the AO07-prefixed token should produce a row.
        "AO090011000743\tAO070340000164\tAO080523000711\tASPL0000280980\n",
        encoding="utf-8",
    )
    rows = from_gene_aliases_file(
        aliases_path,
        fungidb_gene_ids={"AO090011000743"},
        reference_version="FungiDB_v71",
        source_file="aliases.txt",
        source_checksum="cafef00d",
    )
    assert len(rows) == 1
    assert rows[0].external_id == "AO070340000164"
