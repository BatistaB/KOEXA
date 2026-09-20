"""Tests for aoryzae_atlas.database.queries (spec section 25, Milestone 4)."""
from __future__ import annotations

import duckdb

from aoryzae_atlas.database.migrate import apply_migrations
from aoryzae_atlas.database.queries import sample_status_counts


def test_sample_status_counts_empty_dict_when_no_database(tmp_path):
    assert sample_status_counts(tmp_path / "missing.duckdb") == {}


def test_sample_status_counts_buckets_by_state(tmp_path):
    db_path = tmp_path / "test.duckdb"
    apply_migrations(db_path)
    conn = duckdb.connect(str(db_path))
    try:
        conn.execute(
            """
            INSERT INTO samples (sample_id, pipeline_status) VALUES
            ('SRR1', 'METADATA_REVIEW'),
            ('SRR2', 'APPROVED'),
            ('SRR3', 'QUEUED'),
            ('SRR4', 'DOWNLOADING'),
            ('SRR5', 'QUANTIFYING'),
            ('SRR6', 'ARCHIVED'),
            ('SRR7', 'QC_FAILED'),
            ('SRR8', 'EXCLUDED')
            """
        )
    finally:
        conn.close()

    counts = sample_status_counts(db_path)
    assert counts["discovered"] == 8
    assert counts["approved"] == 1
    assert counts["queued"] == 1
    assert counts["processing"] == 2  # DOWNLOADING + QUANTIFYING
    assert counts["archived"] == 1
    assert counts["qc_failed"] == 1
    assert counts["excluded"] == 1
