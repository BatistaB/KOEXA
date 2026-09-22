"""Tests for aoryzae_atlas.database.ingest_conditions (Milestone 6)."""
from __future__ import annotations

import duckdb
import pytest

from aoryzae_atlas.database.ingest_conditions import (
    UnknownSampleError,
    load_conditions,
    load_sample_condition_links,
)
from aoryzae_atlas.database.migrate import apply_migrations

CONDITIONS_HEADER = (
    "condition_id\tcondition_label\tstrain\tmedium\tculture_mode\tcarbon_source\t"
    "nitrogen_source\tsubstrate\ttemperature_C\tpH\ttime_value\ttime_unit\tstress\t"
    "treatment\toxygen_condition\tdevelopmental_stage\trecombinant_background\t"
    "production_context\toriginal_description\tmetadata_confidence\tmetadata_source\n"
)
SAMPLES_HEADER = (
    "sample_id\trun_accession\tbiosample\texperiment_accession\tbioproject\tgeo_sample\t"
    "strain\tcondition_id\treplicate_group\tbiological_replicate\ttechnical_replicate\t"
    "library_layout\tlibrary_strategy\tlibrary_source\tread_length\tread_count\t"
    "download_size\tpipeline_status\tqc_status\tquant_status\treference_version\t"
    "pipeline_version\traw_deleted\texclusion_reason\tcreated_at\tupdated_at\n"
)


@pytest.fixture
def conn(tmp_path):
    db_path = tmp_path / "test.duckdb"
    apply_migrations(db_path)
    connection = duckdb.connect(str(db_path))
    yield connection
    connection.close()


def _seed_sample(conn, sample_id: str) -> None:
    conn.execute(
        "INSERT INTO samples (sample_id, run_accession, pipeline_status) VALUES (?, ?, 'QUANTIFIED')",
        [sample_id, sample_id],
    )


def test_load_conditions(tmp_path, conn):
    path = tmp_path / "conditions.tsv"
    path.write_text(
        CONDITIONS_HEADER
        + "cond1\tRIB40 | glucose | 30C\tRIB40\tCD\tsubmerged\tglucose\t\t\t30\t\t2\tday\t\t\t\t\twild_type\t\tdesc\thigh\tsource\n",
        encoding="utf-8",
    )
    n = load_conditions(conn, path)
    assert n == 1
    row = conn.execute("SELECT condition_id, temperature_C, time_value FROM conditions").fetchone()
    assert row == ("cond1", 30.0, 2.0)


def test_load_conditions_truncates_and_reloads(tmp_path, conn):
    path = tmp_path / "conditions.tsv"
    path.write_text(CONDITIONS_HEADER + "cond1\tlabel\tRIB40\t\t\t\t\t\t\t\t\t\t\t\t\t\t\t\tdesc\thigh\tsrc\n", encoding="utf-8")
    load_conditions(conn, path)
    path.write_text(CONDITIONS_HEADER + "cond2\tlabel2\tRIB40\t\t\t\t\t\t\t\t\t\t\t\t\t\t\t\tdesc\thigh\tsrc\n", encoding="utf-8")
    load_conditions(conn, path)
    ids = [r[0] for r in conn.execute("SELECT condition_id FROM conditions").fetchall()]
    assert ids == ["cond2"]


def test_load_sample_condition_links(tmp_path, conn):
    _seed_sample(conn, "SRR1")
    _seed_sample(conn, "SRR2")
    path = tmp_path / "samples.tsv"
    path.write_text(
        SAMPLES_HEADER
        + "SRR1\tSRR1\t\t\t\t\t\tcond1\tcond1_bio1\t1\t1\t\t\t\t\t\t\tQUANTIFIED\t\t\t\t\t\t\t\t\n"
        + "SRR2\tSRR2\t\t\t\t\t\t\t\t\t\t\t\t\t\t\t\tQUANTIFIED\t\t\t\t\t\t\t\t\n",
        encoding="utf-8",
    )
    n = load_sample_condition_links(conn, path)
    # Only SRR1 has a non-empty condition_id; SRR2 is skipped, not linked.
    assert n == 1
    row = conn.execute(
        "SELECT condition_id, replicate_group, biological_replicate, technical_replicate FROM samples WHERE sample_id = 'SRR1'"
    ).fetchone()
    assert row == ("cond1", "cond1_bio1", "1", "1")
    row2 = conn.execute("SELECT condition_id FROM samples WHERE sample_id = 'SRR2'").fetchone()
    assert row2 == (None,)


def test_load_sample_condition_links_never_resets_other_columns(tmp_path, conn):
    _seed_sample(conn, "SRR1")
    conn.execute("UPDATE samples SET qc_status = 'PASSED' WHERE sample_id = 'SRR1'")
    path = tmp_path / "samples.tsv"
    path.write_text(
        SAMPLES_HEADER + "SRR1\tSRR1\t\t\t\t\t\tcond1\tcond1_bio1\t1\t1\t\t\t\t\t\t\tQUANTIFIED\t\t\t\t\t\t\t\t\n",
        encoding="utf-8",
    )
    load_sample_condition_links(conn, path)
    qc_status = conn.execute("SELECT qc_status FROM samples WHERE sample_id = 'SRR1'").fetchone()[0]
    assert qc_status == "PASSED"


def test_load_sample_condition_links_rejects_unknown_sample(tmp_path, conn):
    path = tmp_path / "samples.tsv"
    path.write_text(
        SAMPLES_HEADER + "GHOST\tGHOST\t\t\t\t\t\tcond1\tcond1_bio1\t1\t1\t\t\t\t\t\t\tQUANTIFIED\t\t\t\t\t\t\t\t\n",
        encoding="utf-8",
    )
    with pytest.raises(UnknownSampleError):
        load_sample_condition_links(conn, path)
