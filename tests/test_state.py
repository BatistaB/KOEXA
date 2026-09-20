"""Tests for the sample state machine (spec section 6)."""
from __future__ import annotations

from aoryzae_atlas.state import FAILURE_STATES, RAW_DELETION_ELIGIBLE_STATES, SampleState


def test_all_spec_states_present():
    expected = {
        "DISCOVERED", "METADATA_REVIEW", "APPROVED", "QUEUED", "DOWNLOADING",
        "DOWNLOADED", "QC_RUNNING", "QC_FAILED", "QUANTIFYING", "QUANT_FAILED",
        "QUANTIFIED", "VALIDATING", "VALIDATION_FAILED", "QC_PASSED",
        "ARCHIVED", "RAW_DELETED", "EXCLUDED", "RETRY",
    }
    actual = {s.value for s in SampleState}
    assert actual == expected


def test_raw_deletion_eligible_states_are_terminal_success_states():
    assert SampleState.ARCHIVED in RAW_DELETION_ELIGIBLE_STATES
    assert SampleState.QC_FAILED not in RAW_DELETION_ELIGIBLE_STATES
    assert SampleState.DOWNLOADING not in RAW_DELETION_ELIGIBLE_STATES


def test_failure_states_disjoint_from_deletion_eligible_states():
    assert FAILURE_STATES.isdisjoint(RAW_DELETION_ELIGIBLE_STATES)
