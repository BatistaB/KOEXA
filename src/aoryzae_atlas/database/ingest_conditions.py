"""Load metadata/conditions.tsv and the condition-linkage columns of
metadata/samples.tsv into DuckDB (Milestone 6: "curate structured
condition metadata" / "confirm sample/run/technical-replicate
distinctions", PROJECT_MASTER_SPEC.md section 37).

`conditions` is fully derived from the curated TSV: truncate and reload,
same policy as ingest_genes.py (nothing here is only-in-the-database).

`samples` rows are updated, not replaced, and only four columns are ever
touched (condition_id, replicate_group, biological_replicate,
technical_replicate) -- every other samples column is owned by discovery
ingestion (ingest_discovery.py) or results ingestion (ingest_results.py)
and must not be reset here. A sample_id in the curation TSV that doesn't
exist in `samples` yet is an error, not a silent insert: condition
curation follows discovery, never precedes it.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import duckdb
import pandas as pd

__all__ = ["UnknownSampleError", "load_conditions", "load_sample_condition_links"]


class UnknownSampleError(Exception):
    """Raised when the samples curation TSV references a sample_id not yet in the `samples` table."""


def load_conditions(conn: duckdb.DuckDBPyConnection, conditions_tsv: Path) -> int:
    frame = pd.read_csv(conditions_tsv, sep="\t", dtype=str, keep_default_na=False)
    conn.execute("DELETE FROM conditions")
    conn.register("conditions_frame", frame)
    conn.execute(
        """
        INSERT INTO conditions (
            condition_id, condition_label, strain, medium, culture_mode, carbon_source,
            nitrogen_source, substrate, temperature_C, pH, time_value, time_unit, stress,
            treatment, oxygen_condition, developmental_stage, recombinant_background,
            production_context, original_description, metadata_confidence, metadata_source
        )
        SELECT
            condition_id, condition_label, strain, medium, culture_mode,
            NULLIF(carbon_source, ''), NULLIF(nitrogen_source, ''), NULLIF(substrate, ''),
            NULLIF(temperature_C, '')::DOUBLE, NULLIF(pH, '')::DOUBLE,
            NULLIF(time_value, '')::DOUBLE, NULLIF(time_unit, ''), NULLIF(stress, ''),
            NULLIF(treatment, ''), NULLIF(oxygen_condition, ''), NULLIF(developmental_stage, ''),
            NULLIF(recombinant_background, ''), NULLIF(production_context, ''),
            original_description, metadata_confidence, metadata_source
        FROM conditions_frame
        """
    )
    conn.unregister("conditions_frame")
    return len(frame)


def load_sample_condition_links(conn: duckdb.DuckDBPyConnection, samples_curation_tsv: Path) -> int:
    frame = pd.read_csv(samples_curation_tsv, sep="\t", dtype=str, keep_default_na=False)
    frame = frame[frame["condition_id"] != ""]
    if frame.empty:
        return 0

    known_ids = {
        row[0]
        for row in conn.execute(
            "SELECT sample_id FROM samples WHERE sample_id IN "
            + "(" + ",".join("?" * len(frame)) + ")",
            list(frame["sample_id"]),
        ).fetchall()
    }
    missing = sorted(set(frame["sample_id"]) - known_ids)
    if missing:
        raise UnknownSampleError(
            f"{len(missing)} sample_id(s) in {samples_curation_tsv} are not in the `samples` "
            f"table yet (run 'atlas database load-discovery' first): {', '.join(missing[:10])}"
            + (", ..." if len(missing) > 10 else "")
        )

    now = datetime.now(timezone.utc)
    for _, row in frame.iterrows():
        conn.execute(
            "UPDATE samples SET condition_id = ?, replicate_group = ?, biological_replicate = ?, "
            "technical_replicate = ?, updated_at = ? WHERE sample_id = ?",
            [
                row["condition_id"],
                row["replicate_group"] or None,
                row["biological_replicate"] or None,
                row["technical_replicate"] or None,
                now,
                row["sample_id"],
            ],
        )
    return len(frame)
