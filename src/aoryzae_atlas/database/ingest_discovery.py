"""Load reports/discovery/{studies,runs}.tsv into DuckDB (the "STORE METADATA"
step of the DISCOVER -> STORE METADATA -> REVIEW -> APPROVE -> QUEUE -> PROCESS
workflow, PROJECT_MASTER_SPEC.md section 23).

Reads the already-written discovery report rather than re-querying
pysradb, so ingestion never touches the network and can be re-run anytime
after `atlas discovery report`.

`samples` rows are upserted, not replaced: `pipeline_status`,
`qc_status`, `quant_status`, and `exclusion_reason` are only set when a
run is first seen. A later re-discovery run must never reset a sample that
has since been approved/queued/processed back to its initial discovery
status -- that would silently erase real pipeline progress.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import duckdb
import pandas as pd

from ..state import SampleState
from .study_groups import group_description

_DISCOVERY_STATUS_TO_SAMPLE_STATE = {
    "REQUIRES_REVIEW": SampleState.METADATA_REVIEW.value,
    "EXCLUDE": SampleState.EXCLUDED.value,
}


def _join_unique(values) -> str:
    return "; ".join(dict.fromkeys(v for v in values if v))


def _collapse_grouped_datasets(frame: pd.DataFrame, groups: dict[str, str]) -> pd.DataFrame:
    """One dataset row per study group in place of its member BioProjects' rows."""
    member_mask = frame["bioproject"].isin(groups)
    collapsed = []
    for study_id in sorted(set(frame.loc[member_mask, "bioproject"].map(groups))):
        members = frame[member_mask & (frame["bioproject"].map(groups) == study_id)]
        row = {column: _join_unique(members[column]) for column in frame.columns}
        row.update(
            dataset_id=study_id,
            bioproject=study_id,
            study_description=group_description(sorted(members["study_description"]), len(members)),
            discovery_date=min(members["discovery_date"]),
            notes=f"Study group {study_id}; member BioProjects: " + ", ".join(sorted(members["bioproject"])),
        )
        collapsed.append(row)
    return pd.concat([frame[~member_mask], pd.DataFrame(collapsed, columns=frame.columns)], ignore_index=True)


def load_datasets(conn: duckdb.DuckDBPyConnection, studies_tsv: Path, groups: dict[str, str] | None = None) -> int:
    frame = pd.read_csv(studies_tsv, sep="\t", dtype=str, keep_default_na=False)
    if groups:
        # Rows loaded before the group existed would otherwise linger beside the group's row.
        conn.execute(f"DELETE FROM datasets WHERE bioproject IN ({','.join('?' * len(groups))})", list(groups))
        frame = _collapse_grouped_datasets(frame, groups)
    conn.register("datasets_frame", frame)
    conn.execute(
        """
        INSERT INTO datasets
        SELECT dataset_id, bioproject, geo_accession, publication_doi, publication_title,
               organism, strain, study_description, source_repository, discovery_date,
               metadata_status, notes
        FROM datasets_frame
        ON CONFLICT (dataset_id) DO UPDATE SET
            bioproject = excluded.bioproject,
            geo_accession = excluded.geo_accession,
            publication_doi = excluded.publication_doi,
            publication_title = excluded.publication_title,
            organism = excluded.organism,
            strain = excluded.strain,
            study_description = excluded.study_description,
            source_repository = excluded.source_repository,
            notes = excluded.notes
        """
    )
    conn.unregister("datasets_frame")
    return len(frame)


def load_samples(
    conn: duckdb.DuckDBPyConnection, runs_tsv: Path, samples_tsv: Path, groups: dict[str, str] | None = None
) -> int:
    runs = pd.read_csv(runs_tsv, sep="\t", dtype=str, keep_default_na=False)
    samples = pd.read_csv(samples_tsv, sep="\t", dtype=str, keep_default_na=False)
    strain_by_biosample = dict(zip(samples["biosample"], samples["strain"]))

    groups = groups or {}
    now = datetime.now(timezone.utc)
    rows = []
    for _, run in runs.iterrows():
        status = run["status"]
        rows.append(
            {
                "sample_id": run["run_accession"],
                "run_accession": run["run_accession"],
                "biosample": run["biosample"],
                "experiment_accession": run["experiment_accession"],
                "bioproject": groups.get(run["bioproject"], run["bioproject"]),
                "source_bioproject": run["bioproject"],
                "strain": strain_by_biosample.get(run["biosample"], ""),
                "library_layout": run["library_layout"],
                "library_strategy": run["library_strategy"],
                "library_source": run["library_source"],
                "read_count": pd.to_numeric(run["total_spots"], errors="coerce"),
                "download_size": pd.to_numeric(run["run_size_bytes"], errors="coerce"),
                "pipeline_status": _DISCOVERY_STATUS_TO_SAMPLE_STATE.get(status, status),
                "exclusion_reason": run["reason"] if status == "EXCLUDE" else "",
                "created_at": now,
                "updated_at": now,
            }
        )
    frame = pd.DataFrame(rows)

    conn.register("samples_frame", frame)
    conn.execute(
        """
        INSERT INTO samples (
            sample_id, run_accession, biosample, experiment_accession, bioproject, source_bioproject,
            strain, library_layout, library_strategy, library_source, read_count,
            download_size, pipeline_status, exclusion_reason, created_at, updated_at
        )
        SELECT sample_id, run_accession, biosample, experiment_accession, bioproject, source_bioproject,
               strain, library_layout, library_strategy, library_source, read_count,
               download_size, pipeline_status, exclusion_reason, created_at, updated_at
        FROM samples_frame
        ON CONFLICT (sample_id) DO UPDATE SET
            biosample = excluded.biosample,
            experiment_accession = excluded.experiment_accession,
            bioproject = excluded.bioproject,
            source_bioproject = excluded.source_bioproject,
            strain = excluded.strain,
            library_layout = excluded.library_layout,
            library_strategy = excluded.library_strategy,
            library_source = excluded.library_source,
            read_count = excluded.read_count,
            download_size = excluded.download_size,
            updated_at = excluded.updated_at
        """
    )
    conn.unregister("samples_frame")
    return len(frame)
