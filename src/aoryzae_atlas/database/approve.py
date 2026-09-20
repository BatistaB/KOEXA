"""Sample approval: the human sign-off gate between discovery and
download/processing (PROJECT_MASTER_SPEC.md section 23's DISCOVER ->
STORE METADATA -> REVIEW -> APPROVE -> QUEUE -> PROCESS workflow). Never
downloads or processes anything itself.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

import duckdb

from ..state import SampleState


class SampleNotFoundError(Exception):
    """Raised when the sample_id isn't in the database yet (not discovered/loaded)."""


class SampleExcludedError(Exception):
    """Raised when trying to approve a sample whose pipeline_status is EXCLUDED."""


@dataclass(frozen=True)
class ApprovalResult:
    sample_id: str
    previous_status: str
    already_approved: bool


def approve_sample(conn: duckdb.DuckDBPyConnection, sample_id: str, reason: str = "") -> ApprovalResult:
    row = conn.execute("SELECT pipeline_status FROM samples WHERE sample_id = ?", [sample_id]).fetchone()
    if row is None:
        raise SampleNotFoundError(sample_id)
    current_status = row[0]

    if current_status == SampleState.APPROVED.value:
        return ApprovalResult(sample_id=sample_id, previous_status=current_status, already_approved=True)
    if current_status == SampleState.EXCLUDED.value:
        raise SampleExcludedError(sample_id)

    now = datetime.now(timezone.utc)
    conn.execute(
        "UPDATE samples SET pipeline_status = ?, updated_at = ? WHERE sample_id = ?",
        [SampleState.APPROVED.value, now, sample_id],
    )
    next_event_id = conn.execute("SELECT COALESCE(MAX(event_id), 0) + 1 FROM processing_events").fetchone()[0]
    conn.execute(
        "INSERT INTO processing_events (event_id, sample_id, event_type, event_detail, created_at) "
        "VALUES (?, ?, 'approved', ?, ?)",
        [next_event_id, sample_id, reason, now],
    )
    return ApprovalResult(sample_id=sample_id, previous_status=current_status, already_approved=False)
