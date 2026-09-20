"""Tests for atomic runtime/status.json read-write (spec section 27)."""
from __future__ import annotations

from aoryzae_atlas import runtime_status as rs


def test_init_runtime_status_is_idempotent(tmp_path, monkeypatch):
    status_file = tmp_path / "status.json"
    monkeypatch.setattr(rs, "RUNTIME_STATUS_FILE", status_file)

    first = rs.init_runtime_status()
    assert status_file.is_file()

    second = rs.init_runtime_status()
    assert second.initialized_at == first.initialized_at  # not clobbered


def test_save_and_load_roundtrip(tmp_path, monkeypatch):
    status_file = tmp_path / "status.json"
    monkeypatch.setattr(rs, "RUNTIME_STATUS_FILE", status_file)

    status = rs.init_runtime_status()
    status.current_sample = "SRR0000001"
    status.next_resumable_step = "quantify"
    rs.save_runtime_status(status)

    reloaded = rs.load_runtime_status()
    assert reloaded is not None
    assert reloaded.current_sample == "SRR0000001"
    assert reloaded.next_resumable_step == "quantify"


def test_load_runtime_status_returns_none_when_absent(tmp_path, monkeypatch):
    monkeypatch.setattr(rs, "RUNTIME_STATUS_FILE", tmp_path / "does-not-exist.json")
    assert rs.load_runtime_status() is None


def test_atomic_write_leaves_no_tmp_file_on_success(tmp_path, monkeypatch):
    status_file = tmp_path / "status.json"
    monkeypatch.setattr(rs, "RUNTIME_STATUS_FILE", status_file)
    rs.init_runtime_status()
    leftovers = [p for p in tmp_path.iterdir() if p.name.startswith(".tmp-status-")]
    assert leftovers == []
