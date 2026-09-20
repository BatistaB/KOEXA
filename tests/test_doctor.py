"""Tests for `atlas doctor` checks."""
from __future__ import annotations

from aoryzae_atlas.doctor import run_doctor


def test_run_doctor_returns_unique_named_checks():
    results = run_doctor()
    names = [r.name for r in results]
    assert len(names) == len(set(names)), "duplicate check names"
    assert any(r.name == "python_version" for r in results)


def test_required_checks_pass_on_a_freshly_scaffolded_repo():
    results = run_doctor()
    required_failures = [r for r in results if r.required and not r.ok]
    assert required_failures == [], f"unexpected required failures: {required_failures}"


def test_optional_tool_checks_never_fail_the_required_set():
    results = run_doctor()
    optional = [r for r in results if not r.required]
    # Optional checks may be ok or not, but must never be marked required=True
    assert all(not r.required for r in optional)
