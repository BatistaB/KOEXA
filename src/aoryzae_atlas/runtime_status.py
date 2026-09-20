"""Read/write runtime/status.json atomically.

This is the lightweight, human-inspectable status file the CLI shell uses
before the DuckDB-backed database exists (Milestone 4). It intentionally
stores only coarse, resumability-relevant information; per-sample state
belongs in the database once it exists.
"""
from __future__ import annotations

import json
import os
import tempfile
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .paths import RUNTIME_DIR, RUNTIME_STATUS_FILE


def _utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass
class RuntimeStatus:
    schema_version: int = 1
    initialized_at: str = field(default_factory=_utcnow_iso)
    last_updated_at: str = field(default_factory=_utcnow_iso)
    current_sample: str | None = None
    next_resumable_step: str | None = None
    nextflow_run_name: str | None = None
    nextflow_session_id: str | None = None
    last_pipeline_version: str | None = None
    last_reference_version: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _atomic_write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(dir=str(path.parent), prefix=".tmp-status-", suffix=".json")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2, sort_keys=True)
            fh.write("\n")
        os.replace(tmp_name, path)
    except Exception:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise


def load_runtime_status() -> RuntimeStatus | None:
    if not RUNTIME_STATUS_FILE.is_file():
        return None
    with RUNTIME_STATUS_FILE.open("r", encoding="utf-8") as fh:
        data = json.load(fh)
    known_fields = {f for f in RuntimeStatus.__dataclass_fields__}
    filtered = {k: v for k, v in data.items() if k in known_fields}
    return RuntimeStatus(**filtered)


def init_runtime_status(force: bool = False) -> RuntimeStatus:
    """Create runtime/status.json if it does not already exist.

    Never overwrites an existing status file unless force=True, so re-running
    `atlas init` cannot silently discard resumability information.
    """
    if RUNTIME_STATUS_FILE.is_file() and not force:
        existing = load_runtime_status()
        if existing is not None:
            return existing
    status = RuntimeStatus()
    _atomic_write_json(RUNTIME_STATUS_FILE, status.to_dict())
    return status


def save_runtime_status(status: RuntimeStatus) -> None:
    status.last_updated_at = _utcnow_iso()
    _atomic_write_json(RUNTIME_STATUS_FILE, status.to_dict())
