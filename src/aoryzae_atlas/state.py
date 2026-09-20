"""Sample state machine, per PROJECT_MASTER_SPEC.md section 6.

This module only defines the vocabulary and legal-ish transitions for
Milestone 0. The database module (added in Milestone 4) is responsible for
persisting state transitions with timestamps; nothing here touches disk.
"""
from __future__ import annotations

from enum import Enum


class SampleState(str, Enum):
    DISCOVERED = "DISCOVERED"
    METADATA_REVIEW = "METADATA_REVIEW"
    APPROVED = "APPROVED"
    QUEUED = "QUEUED"
    DOWNLOADING = "DOWNLOADING"
    DOWNLOADED = "DOWNLOADED"
    QC_RUNNING = "QC_RUNNING"
    QC_FAILED = "QC_FAILED"
    QUANTIFYING = "QUANTIFYING"
    QUANT_FAILED = "QUANT_FAILED"
    QUANTIFIED = "QUANTIFIED"
    VALIDATING = "VALIDATING"
    VALIDATION_FAILED = "VALIDATION_FAILED"
    QC_PASSED = "QC_PASSED"
    ARCHIVED = "ARCHIVED"
    RAW_DELETED = "RAW_DELETED"
    EXCLUDED = "EXCLUDED"
    RETRY = "RETRY"


# Terminal-ish states after which raw deletion is permitted, per the Storage
# Guardian deletion rules (spec section 5). This is descriptive metadata for
# future storage-module use, not an enforcement mechanism by itself.
RAW_DELETION_ELIGIBLE_STATES = {
    SampleState.ARCHIVED,
    SampleState.RAW_DELETED,
}

FAILURE_STATES = {
    SampleState.QC_FAILED,
    SampleState.QUANT_FAILED,
    SampleState.VALIDATION_FAILED,
}
