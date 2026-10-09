"""Tests for aoryzae_atlas.database.ingest_results (docs/decisions/0004)."""
from __future__ import annotations

import json

import duckdb
import pytest

from aoryzae_atlas.database.approve import SampleExcludedError, SampleNotFoundError
from aoryzae_atlas.database.ingest_results import (
    ResultsIncompleteError,
    ResultsNotFoundError,
    find_ingestable_accessions,
    ingest_sample_results,
)
from aoryzae_atlas.database.migrate import apply_migrations

GENE_QUANT_TSV = "gene_id\tTPM\tNumReads\nAO090001000001\t10.5\t100.0\nAO090001000002\t0.0\t0.0\n"

FASTP_JSON = {
    "summary": {
        "before_filtering": {"total_reads": 1000, "q30_rate": 0.9},
        "after_filtering": {"total_reads": 950, "q30_rate": 0.95, "q20_rate": 0.98, "gc_content": 0.5},
    },
    "filtering_result": {"passed_filter_reads": 950},
    "duplication": {"rate": 0.1},
}


@pytest.fixture
def conn(tmp_path):
    db_path = tmp_path / "test.duckdb"
    apply_migrations(db_path)
    connection = duckdb.connect(str(db_path))
    connection.execute("INSERT INTO samples (sample_id, pipeline_status) VALUES ('DRR1', 'APPROVED')")
    yield connection
    connection.close()


def _write_sample_dir(results_dir, accession, with_fastp=True, with_done=True, with_gene_quant=True):
    sample_dir = results_dir / accession
    sample_dir.mkdir(parents=True)
    if with_gene_quant:
        (sample_dir / "gene_quant.tsv").write_text(GENE_QUANT_TSV, encoding="utf-8")
    if with_fastp:
        (sample_dir / "fastp.json").write_text(json.dumps(FASTP_JSON), encoding="utf-8")
    if with_done:
        (sample_dir / "DONE").write_text("ok", encoding="utf-8")
    return sample_dir


def test_ingest_sample_results_loads_genes_and_qc_and_updates_status(tmp_path, conn):
    _write_sample_dir(tmp_path, "DRR1")

    result = ingest_sample_results(conn, "DRR1", tmp_path, pipeline_version="0.2.0", reference_version="RIB40_v1")

    assert result.previous_status == "APPROVED"
    assert result.n_genes == 2

    genes = conn.execute(
        "SELECT canonical_gene_id, TPM, estimated_counts, effective_length FROM gene_expression "
        "WHERE sample_id = 'DRR1' ORDER BY canonical_gene_id"
    ).fetchall()
    assert genes == [
        ("AO090001000001", 10.5, 100.0, None),
        ("AO090001000002", 0.0, 0.0, None),
    ]

    qc = dict(
        conn.execute("SELECT metric_name, metric_value FROM sample_qc WHERE sample_id = 'DRR1'").fetchall()
    )
    assert qc["fastp_q30_rate_after"] == 0.95
    assert qc["salmon_total_gene_assigned_counts"] == 100.0

    row = conn.execute(
        "SELECT pipeline_status, reference_version, pipeline_version FROM samples WHERE sample_id = 'DRR1'"
    ).fetchone()
    assert row == ("QUANTIFIED", "RIB40_v1", "0.2.0")

    event = conn.execute(
        "SELECT event_type FROM processing_events WHERE sample_id = 'DRR1'"
    ).fetchone()
    assert event == ("ingested",)


def test_ingest_sample_results_without_fastp_still_records_salmon_metric(tmp_path, conn):
    _write_sample_dir(tmp_path, "DRR1", with_fastp=False)
    result = ingest_sample_results(conn, "DRR1", tmp_path)
    assert result.n_qc_metrics == 1
    qc = dict(conn.execute("SELECT metric_name, metric_value FROM sample_qc WHERE sample_id = 'DRR1'").fetchall())
    assert qc == {"salmon_total_gene_assigned_counts": 100.0}


def test_ingest_sample_results_is_rerunnable_without_duplicating_rows(tmp_path, conn):
    _write_sample_dir(tmp_path, "DRR1")
    ingest_sample_results(conn, "DRR1", tmp_path)
    ingest_sample_results(conn, "DRR1", tmp_path)

    n_genes = conn.execute("SELECT COUNT(*) FROM gene_expression WHERE sample_id = 'DRR1'").fetchone()[0]
    n_qc = conn.execute("SELECT COUNT(*) FROM sample_qc WHERE sample_id = 'DRR1'").fetchone()[0]
    assert n_genes == 2
    assert n_qc == 9


def test_ingest_sample_results_raises_for_unknown_sample(tmp_path, conn):
    _write_sample_dir(tmp_path, "DRR_UNKNOWN")
    with pytest.raises(SampleNotFoundError):
        ingest_sample_results(conn, "DRR_UNKNOWN", tmp_path)


def test_ingest_sample_results_raises_when_folder_missing(tmp_path, conn):
    with pytest.raises(ResultsNotFoundError):
        ingest_sample_results(conn, "DRR1", tmp_path)


def test_ingest_sample_results_raises_when_done_marker_missing(tmp_path, conn):
    _write_sample_dir(tmp_path, "DRR1", with_done=False)
    with pytest.raises(ResultsIncompleteError):
        ingest_sample_results(conn, "DRR1", tmp_path)


def test_ingest_sample_results_raises_when_gene_quant_missing(tmp_path, conn):
    _write_sample_dir(tmp_path, "DRR1", with_gene_quant=False)
    with pytest.raises(ResultsIncompleteError):
        ingest_sample_results(conn, "DRR1", tmp_path)


def test_find_ingestable_accessions_only_lists_done_folders(tmp_path):
    _write_sample_dir(tmp_path, "DRR2")
    _write_sample_dir(tmp_path, "DRR1", with_done=False)
    (tmp_path / "logs").mkdir()

    assert find_ingestable_accessions(tmp_path) == ["DRR2"]


def test_find_ingestable_accessions_returns_empty_list_for_missing_dir(tmp_path):
    assert find_ingestable_accessions(tmp_path / "does_not_exist") == []


def test_ingest_sample_results_refuses_excluded_sample(tmp_path, conn):
    conn.execute("UPDATE samples SET pipeline_status = 'EXCLUDED' WHERE sample_id = 'DRR1'")
    _write_sample_dir(tmp_path, "DRR1")
    with pytest.raises(SampleExcludedError):
        ingest_sample_results(conn, "DRR1", tmp_path)
    assert conn.execute("SELECT pipeline_status FROM samples WHERE sample_id = 'DRR1'").fetchone()[0] == "EXCLUDED"
    assert conn.execute("SELECT COUNT(*) FROM gene_expression WHERE sample_id = 'DRR1'").fetchone()[0] == 0
