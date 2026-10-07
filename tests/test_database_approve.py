"""Tests for aoryzae_atlas.database.approve (spec section 23, Milestone 4/5)."""
from __future__ import annotations

import duckdb
import pytest

from aoryzae_atlas.database.approve import (
    SampleExcludedError,
    SampleNotApprovedError,
    SampleNotFoundError,
    approve_sample,
    unapprove_sample,
)
from aoryzae_atlas.database.migrate import apply_migrations


@pytest.fixture
def conn(tmp_path):
    db_path = tmp_path / "test.duckdb"
    apply_migrations(db_path)
    connection = duckdb.connect(str(db_path))
    connection.execute(
        """
        INSERT INTO samples (sample_id, pipeline_status) VALUES
        ('SRR1', 'METADATA_REVIEW'),
        ('SRR2', 'EXCLUDED'),
        ('SRR3', 'APPROVED')
        """
    )
    yield connection
    connection.close()


def test_approve_sample_updates_status_and_logs_event(conn):
    result = approve_sample(conn, "SRR1", reason="Milestone 5 first end-to-end test")
    assert result.previous_status == "METADATA_REVIEW"
    assert result.already_approved is False

    status = conn.execute("SELECT pipeline_status FROM samples WHERE sample_id = 'SRR1'").fetchone()[0]
    assert status == "APPROVED"

    event = conn.execute(
        "SELECT sample_id, event_type, event_detail FROM processing_events WHERE sample_id = 'SRR1'"
    ).fetchone()
    assert event == ("SRR1", "approved", "Milestone 5 first end-to-end test")


def test_approve_sample_raises_for_unknown_sample(conn):
    with pytest.raises(SampleNotFoundError):
        approve_sample(conn, "SRR_DOES_NOT_EXIST")


def test_approve_sample_raises_for_excluded_sample(conn):
    with pytest.raises(SampleExcludedError):
        approve_sample(conn, "SRR2")
    # Must not have been silently changed.
    status = conn.execute("SELECT pipeline_status FROM samples WHERE sample_id = 'SRR2'").fetchone()[0]
    assert status == "EXCLUDED"


def test_approve_sample_is_idempotent_for_already_approved(conn):
    result = approve_sample(conn, "SRR3")
    assert result.already_approved is True
    assert result.previous_status == "APPROVED"
    # No duplicate processing_events row for a no-op approval.
    n_events = conn.execute("SELECT COUNT(*) FROM processing_events WHERE sample_id = 'SRR3'").fetchone()[0]
    assert n_events == 0


def test_unapprove_sample_returns_to_review_and_logs_event(conn):
    unapprove_sample(conn, "SRR3", reason="raw data not downloadable from ENA")
    status = conn.execute("SELECT pipeline_status FROM samples WHERE sample_id = 'SRR3'").fetchone()[0]
    assert status == "METADATA_REVIEW"
    event = conn.execute(
        "SELECT event_type, event_detail FROM processing_events WHERE sample_id = 'SRR3'"
    ).fetchone()
    assert event == ("unapproved", "raw data not downloadable from ENA")


def test_unapprove_sample_refuses_non_approved_sample(conn):
    with pytest.raises(SampleNotApprovedError):
        unapprove_sample(conn, "SRR1")
    assert conn.execute("SELECT COUNT(*) FROM processing_events").fetchone()[0] == 0


def test_unapprove_sample_raises_for_unknown_sample(conn):
    with pytest.raises(SampleNotFoundError):
        unapprove_sample(conn, "SRR_DOES_NOT_EXIST")
