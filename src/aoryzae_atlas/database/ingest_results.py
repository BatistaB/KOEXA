"""Ingest a Colab-produced results/<accession>/ folder into DuckDB.

Acquisition, FastQC/fastp, and Salmon quantification now run in Google
Colab (docs/decisions/0004-colab-based-acquisition.md), which syncs only
the finished per-sample outputs back here via Google Drive
(workflows/ingest_colab_drop.sh moves them into results/<accession>/).
Nothing before this module closed the loop back into
database/atlas.duckdb -- samples sat APPROVED/RETRY forever despite
already being quantified. This is that missing step.

Re-running for the same sample_id is safe and expected (e.g. after a
corrected Colab re-run): gene_expression/sample_qc rows for that
sample_id are replaced, not duplicated, matching ingest_genes.py's
"truncate and reload" policy for other fully-derived tables.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

import duckdb
import pandas as pd

from .approve import SampleExcludedError, SampleNotFoundError
from ..state import SampleState

__all__ = [
    "SampleExcludedError",
    "SampleNotFoundError",
    "ResultsNotFoundError",
    "ResultsIncompleteError",
    "IngestResult",
    "ingest_sample_results",
    "find_ingestable_accessions",
]


class ResultsNotFoundError(Exception):
    """Raised when results/<accession>/ doesn't exist at all."""


class ResultsIncompleteError(Exception):
    """Raised when results/<accession>/ exists but has no DONE marker, or is
    missing gene_quant.tsv -- an interrupted or corrupted Colab sync, not
    something to guess at ingesting partially."""


@dataclass(frozen=True)
class IngestResult:
    sample_id: str
    previous_status: str
    n_genes: int
    n_qc_metrics: int


def _read_fastp_metrics(fastp_json_path: Path) -> dict[str, float]:
    data = json.loads(fastp_json_path.read_text(encoding="utf-8"))
    summary = data.get("summary", {})
    before = summary.get("before_filtering", {})
    after = summary.get("after_filtering", {})
    filtering = data.get("filtering_result", {})
    duplication = data.get("duplication", {})
    raw = {
        "fastp_q30_rate_before": before.get("q30_rate"),
        "fastp_q30_rate_after": after.get("q30_rate"),
        "fastp_q20_rate_after": after.get("q20_rate"),
        "fastp_gc_content_after": after.get("gc_content"),
        "fastp_total_reads_before": before.get("total_reads"),
        "fastp_total_reads_after": after.get("total_reads"),
        "fastp_passed_filter_reads": filtering.get("passed_filter_reads"),
        "fastp_duplication_rate": duplication.get("rate"),
    }
    return {name: float(value) for name, value in raw.items() if value is not None}


def find_ingestable_accessions(results_dir: Path) -> list[str]:
    """List subdirectories of results_dir that look like a finished Colab
    sample folder (has a DONE marker), sorted for deterministic output."""
    if not results_dir.is_dir():
        return []
    return sorted(
        child.name
        for child in results_dir.iterdir()
        if child.is_dir() and (child / "DONE").is_file()
    )


def ingest_sample_results(
    conn: duckdb.DuckDBPyConnection,
    sample_id: str,
    results_dir: Path,
    pipeline_version: str = "",
    reference_version: str = "",
) -> IngestResult:
    row = conn.execute("SELECT pipeline_status FROM samples WHERE sample_id = ?", [sample_id]).fetchone()
    if row is None:
        raise SampleNotFoundError(sample_id)
    previous_status = row[0]
    if previous_status == SampleState.EXCLUDED.value:
        # An excluded sample's Colab results may still sit in results/; they must not flip it back to QUANTIFIED.
        raise SampleExcludedError(sample_id)

    sample_dir = results_dir / sample_id
    if not sample_dir.is_dir():
        raise ResultsNotFoundError(sample_id)
    if not (sample_dir / "DONE").is_file():
        raise ResultsIncompleteError(sample_id)

    gene_quant_path = sample_dir / "gene_quant.tsv"
    if not gene_quant_path.is_file():
        raise ResultsIncompleteError(sample_id)

    now = datetime.now(timezone.utc)

    gq = pd.read_csv(gene_quant_path, sep="\t", dtype={"gene_id": str})
    gq = gq.rename(columns={"gene_id": "canonical_gene_id", "NumReads": "estimated_counts"})
    gq["sample_id"] = sample_id
    # gene_quant.tsv is a pandas aggregation of transcript-level quant.sf up
    # to gene level (see the Colab notebook's aggregate_to_gene) and doesn't
    # carry a gene-level effective length the way tximport would -- leave it
    # NULL rather than fabricate one.
    gq["effective_length"] = None

    conn.execute("DELETE FROM gene_expression WHERE sample_id = ?", [sample_id])
    conn.register("gq_frame", gq)
    conn.execute(
        """
        INSERT INTO gene_expression (sample_id, canonical_gene_id, TPM, estimated_counts, effective_length)
        SELECT sample_id, canonical_gene_id, TPM, estimated_counts, effective_length FROM gq_frame
        """
    )
    conn.unregister("gq_frame")
    n_genes = len(gq)

    metrics: dict[str, float] = {}
    fastp_json_path = sample_dir / "fastp.json"
    if fastp_json_path.is_file():
        metrics.update(_read_fastp_metrics(fastp_json_path))
    # AFED's own inclusion-gate numerator (TODO.md "AFED's QC/inclusion
    # criteria": total_counts >= 1e6) -- recorded so config/qc.yaml can use
    # it once that gate is implemented; not enforced as a gate here.
    metrics["salmon_total_gene_assigned_counts"] = float(gq["estimated_counts"].sum())

    conn.execute("DELETE FROM sample_qc WHERE sample_id = ?", [sample_id])
    for metric_name, metric_value in metrics.items():
        tool = "fastp" if metric_name.startswith("fastp_") else "salmon"
        conn.execute(
            "INSERT INTO sample_qc (sample_id, metric_name, metric_value, qc_tool, qc_tool_version, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            [sample_id, metric_name, metric_value, tool, "", now],
        )
    n_qc_metrics = len(metrics)

    conn.execute(
        "UPDATE samples SET pipeline_status = ?, reference_version = ?, pipeline_version = ?, updated_at = ? "
        "WHERE sample_id = ?",
        [SampleState.QUANTIFIED.value, reference_version, pipeline_version, now, sample_id],
    )
    next_event_id = conn.execute("SELECT COALESCE(MAX(event_id), 0) + 1 FROM processing_events").fetchone()[0]
    conn.execute(
        "INSERT INTO processing_events (event_id, sample_id, event_type, event_detail, pipeline_version, created_at) "
        "VALUES (?, ?, 'ingested', ?, ?, ?)",
        [next_event_id, sample_id, f"{n_genes} genes, {n_qc_metrics} qc metrics from {sample_dir}", pipeline_version, now],
    )
    return IngestResult(sample_id=sample_id, previous_status=previous_status, n_genes=n_genes, n_qc_metrics=n_qc_metrics)
