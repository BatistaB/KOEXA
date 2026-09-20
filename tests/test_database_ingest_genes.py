"""Tests for aoryzae_atlas.database.ingest_genes (spec section 8, Milestone 4)."""
from __future__ import annotations

import duckdb
import pytest

from aoryzae_atlas.database.ingest_genes import load_gene_external_identifiers, load_genes
from aoryzae_atlas.database.migrate import apply_migrations


@pytest.fixture
def conn(tmp_path):
    db_path = tmp_path / "test.duckdb"
    apply_migrations(db_path)
    connection = duckdb.connect(str(db_path))
    yield connection
    connection.close()


def test_load_genes(tmp_path, conn):
    path = tmp_path / "gene_master.tsv"
    path.write_text(
        "canonical_gene_id\tgene_symbol\tgene_name\tchromosome\tstart\tend\tstrand\tbiotype\tdescription\treference_version\n"
        "AO090001000001\t\t\tChr1\t350\t1289\t+\tprotein_coding\tdesc\tFungiDB_v71\n",
        encoding="utf-8",
    )
    n = load_genes(conn, path)
    assert n == 1
    row = conn.execute("SELECT canonical_gene_id, chromosome, start, \"end\" FROM genes").fetchone()
    assert row == ("AO090001000001", "Chr1", 350, 1289)


def test_load_genes_replaces_existing_rows(tmp_path, conn):
    path = tmp_path / "gene_master.tsv"
    header = "canonical_gene_id\tgene_symbol\tgene_name\tchromosome\tstart\tend\tstrand\tbiotype\tdescription\treference_version\n"
    path.write_text(header + "AO090001000001\t\t\tChr1\t1\t2\t+\tprotein_coding\told\tFungiDB_v71\n", encoding="utf-8")
    load_genes(conn, path)

    path.write_text(header + "AO090001000002\t\t\tChr2\t1\t2\t+\tprotein_coding\tnew\tFungiDB_v71\n", encoding="utf-8")
    n = load_genes(conn, path)
    assert n == 1
    ids = [r[0] for r in conn.execute("SELECT canonical_gene_id FROM genes").fetchall()]
    assert ids == ["AO090001000002"]


def test_load_gene_external_identifiers(tmp_path, conn):
    path = tmp_path / "gxi.tsv"
    path.write_text(
        "canonical_gene_id\tnamespace\texternal_id\texternal_name\tmapping_type\tmapping_confidence\t"
        "mapping_method\tevidence\tsource_file\tsource_version\tsource_checksum\treference_version\n"
        "AO090001000001\tUniProtKB_accession\tQ12345\t\texact\thigh\tm\te\tf\tv\tc\tFungiDB_v71\n",
        encoding="utf-8",
    )
    n = load_gene_external_identifiers(conn, path)
    assert n == 1
    row = conn.execute("SELECT canonical_gene_id, namespace, external_id FROM gene_external_identifiers").fetchone()
    assert row == ("AO090001000001", "UniProtKB_accession", "Q12345")
