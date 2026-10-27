"""Tests for aoryzae_atlas.genesets.curated and the `atlas geneset` commands."""
from __future__ import annotations

import json

import pandas as pd
import pytest
from click.testing import CliRunner

from aoryzae_atlas.cli import main as cli_main
from aoryzae_atlas.genesets.curated import (
    alias_candidates_from_table,
    load_gene_set,
    load_gene_sets,
    parse_gene_list,
    resolve_gene_list,
    write_gene_set,
)

CATALOG = {"AO090000000001", "AO090000000002", "AO090000000003", "AO090000000004"}
REDIRECTS = {"AO090000009991": "AO090000000002", "AO090000009992": "AO090000000002", "AO090000009993": "AO090000000003"}


def test_parse_gene_list_handles_separators_comments_and_keeps_duplicates():
    text = "AO090000000001\nAO090000000002, AO090000000003;  sspB  # a trailing comment\n# whole-line comment\n\nAO090000000001\n"
    assert parse_gene_list(text) == ["AO090000000001", "AO090000000002", "AO090000000003", "sspB", "AO090000000001"]


def test_resolution_statuses_and_only_vetted_ones_are_accepted():
    tokens = ["AO090000000001", "AO090000009991", "AO090000000004-A", "sspB", "mystery", "AO090000000001"]
    aliases = {"AO090000000004-A": ["AO090000000004"]}
    table = resolve_gene_list(tokens, CATALOG, REDIRECTS, aliases, manual_map={"mystery": "AO090000000003"}).set_index("input_id")
    assert table.loc["AO090000000001", "resolution"] == "exact" and table.loc["AO090000000001", "n_occurrences"] == 2
    assert table.loc["AO090000009991", ["resolution", "canonical_gene_id"]].tolist() == ["redirected", "AO090000000002"]
    assert table.loc["mystery", "resolution"] == "manual"
    # an alias is a candidate, never silently accepted; an unknown token stays unresolved
    assert table.loc["AO090000000004-A", "resolution"] == "alias_candidate" and table.loc["AO090000000004-A", "canonical_gene_id"] == ""
    assert "AO090000000004" in table.loc["AO090000000004-A", "note"]
    assert table.loc["sspB", "resolution"] == "unresolved" and len(table) == 5      # distinct tokens only


def test_manual_mapping_to_an_unknown_gene_is_refused():
    with pytest.raises(ValueError, match="not in the catalog"):
        resolve_gene_list(["x"], CATALOG, manual_map={"x": "AO09NOPE"})


def test_alias_candidates_come_from_gene_alias_rows_only():
    table = pd.DataFrame({
        "canonical_gene_id": ["G1", "G2", "G3"], "namespace": ["gene_alias", "gene_alias", "UniProtKB_accession"],
        "external_id": ["oryL", "oryL", "Q1"],
    })
    assert alias_candidates_from_table(table) == {"oryL": ["G1", "G2"]}


def test_write_and_load_roundtrip_merges_tokens_that_reach_one_gene(tmp_path):
    tokens = ["AO090000000001", "AO090000009991", "AO090000009992", "sspB", "AO090000000001"]
    resolution = resolve_gene_list(tokens, CATALOG, REDIRECTS)
    meta = write_gene_set("secreted", resolution, tmp_path, "test set", "unit test", "\n".join(tokens), len(tokens))
    assert meta["n_members"] == 2 and meta["n_duplicate_lines"] == 1 and meta["n_by_resolution"]["unresolved"] == 1
    members = pd.read_csv(tmp_path / "secreted.tsv", sep="\t", dtype=str).set_index("canonical_gene_id")
    assert set(members.index) == {"AO090000000001", "AO090000000002"}
    assert set(members.loc["AO090000000002", "input_ids"].split(";")) == {"AO090000009991", "AO090000009992"}   # two retired ids, one gene
    assert load_gene_set("secreted", tmp_path) == ["AO090000000001", "AO090000000002"]
    assert json.loads((tmp_path / "secreted.json").read_text(encoding="utf-8"))["source"] == "unit test"
    assert load_gene_sets(tmp_path)["secreted"]["genes"] == ["AO090000000001", "AO090000000002"]
    assert load_gene_sets(tmp_path / "missing") == {}


def test_set_names_are_restricted(tmp_path):
    with pytest.raises(ValueError):
        write_gene_set("Bad Name", resolve_gene_list([], CATALOG), tmp_path, "d", "s", "", 0)


def test_cli_import_and_list(tmp_path, monkeypatch):
    master = tmp_path / "gene_master.tsv"
    pd.DataFrame({"canonical_gene_id": sorted(CATALOG)}).to_csv(master, sep="\t", index=False)
    external = tmp_path / "ext.tsv"
    pd.DataFrame({"canonical_gene_id": ["AO090000000004"], "namespace": ["gene_alias"], "external_id": ["AO090000000004-A"]}).to_csv(external, sep="\t", index=False)
    aliases = tmp_path / "aliases.txt"
    aliases.write_text("AO090000000002\tAO090000009991\tAO070000000001\n", encoding="utf-8")
    sets_dir = tmp_path / "sets"
    for name, value in {"GENE_MASTER_FILE": master, "GENE_EXTERNAL_IDENTIFIERS_FILE": external, "FUNGIDB_GENE_ALIASES_FILE": aliases, "GENE_SETS_DIR": sets_dir}.items():
        monkeypatch.setattr(cli_main, name, value)
    listing = tmp_path / "ids.txt"
    listing.write_text("AO090000000001\nAO090000009991\nAO090000000004-A\nsspB\n", encoding="utf-8")

    runner = CliRunner()
    result = runner.invoke(cli_main.cli, ["geneset", "import", "toy", str(listing), "--description", "toy", "--source", "test", "--map", "sspB=AO090000000003"])
    assert result.exit_code == 0, result.output
    assert "3 genes in 'toy'" in result.output and "NOT IN SET: AO090000000004-A  [alias_candidate]" in result.output
    assert load_gene_set("toy", sets_dir) == ["AO090000000001", "AO090000000002", "AO090000000003"]
    listed = runner.invoke(cli_main.cli, ["geneset", "list"])
    assert listed.exit_code == 0 and "toy: 3 genes" in listed.output and "alias_candidate" in listed.output
    bad = runner.invoke(cli_main.cli, ["geneset", "import", "toy2", str(listing), "--description", "d", "--source", "s", "--map", "nonsense"])
    assert bad.exit_code != 0 and "TOKEN=GENE" in bad.output


def test_export_gene_sets_for_the_web(tmp_path, monkeypatch):
    from aoryzae_atlas.webexport import build as webexport

    monkeypatch.setattr(webexport, "GENE_SETS_DIR", tmp_path / "none")
    assert webexport.export_gene_sets() is None                     # nothing imported: the page simply has no filter

    resolution = resolve_gene_list(["AO090000000001", "AO090000009991", "sspB"], CATALOG, REDIRECTS)
    write_gene_set("secreted", resolution, tmp_path / "sets", "toy secretome", "unit test", "x", 3)
    monkeypatch.setattr(webexport, "GENE_SETS_DIR", tmp_path / "sets")
    payload = webexport.export_gene_sets()
    assert payload is not None and set(payload["sets"]) == {"secreted"}
    entry = payload["sets"]["secreted"]
    assert entry["genes"] == ["AO090000000001", "AO090000000002"] and entry["description"] == "toy secretome" and entry["source"] == "unit test"
    json.dumps(payload, allow_nan=False)                            # strict JSON for the browser
