"""Read queries backing `atlas status` (PROJECT_MASTER_SPEC.md section 25, Milestone 4)."""
from __future__ import annotations

from pathlib import Path

import duckdb

from ..state import SampleState

_PROCESSING_STATES = {
    SampleState.DOWNLOADING.value,
    SampleState.DOWNLOADED.value,
    SampleState.QC_RUNNING.value,
    SampleState.QUANTIFYING.value,
    SampleState.VALIDATING.value,
}


def sample_status_counts(db_path: Path) -> dict[str, int]:
    """Counts for the section-25 status block, keyed by that block's own labels.

    Returns an empty dict if the database doesn't exist yet, rather than
    zeros -- "no database" and "database with zero samples" are different
    facts and callers should be able to tell them apart.
    """
    if not db_path.is_file():
        return {}
    conn = duckdb.connect(str(db_path), read_only=True)
    try:
        total = conn.execute("SELECT COUNT(*) FROM samples").fetchone()[0]
        rows = conn.execute("SELECT pipeline_status, COUNT(*) FROM samples GROUP BY 1").fetchall()
    finally:
        conn.close()
    by_status = dict(rows)
    return {
        "discovered": total,
        "approved": by_status.get(SampleState.APPROVED.value, 0),
        "queued": by_status.get(SampleState.QUEUED.value, 0),
        "processing": sum(by_status.get(s, 0) for s in _PROCESSING_STATES),
        "archived": by_status.get(SampleState.ARCHIVED.value, 0),
        "qc_failed": by_status.get(SampleState.QC_FAILED.value, 0),
        "excluded": by_status.get(SampleState.EXCLUDED.value, 0),
    }
