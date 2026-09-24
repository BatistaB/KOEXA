"""Build the JSON snapshots app/web/ fetches at runtime, from DuckDB (the
real ingested samples/conditions/datasets/expression) and the classification
parquet produced by `aoryzae_atlas.clustering.classify` (if it has been run).

Scope: only samples that are QUANTIFIED **and** have a curated condition_id
(the same "real, usable" gate `matrix.build.fetch_sample_condition_map`
uses) are exported. A sample sitting in METADATA_REVIEW/APPROVED, or
QUANTIFIED but not yet condition-curated, does not appear on the site --
curation, not just quantification, is what makes a sample presentable.

Every function here is read-only against the database; nothing is written
back to DuckDB.
"""
from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

import duckdb
import pandas as pd

from ..genome.karyotype import DEFAULT_BIN_SIZE_BP, NUCLEAR_CHROMOSOMES, bin_gene_expression, chromosome_lengths_by_name
from ..paths import CLASSIFICATION_FILE, FUNGIDB_GENOME_FASTA_FILE, GENE_FEATURE_TABLE_FILE, WEB_DATA_DIR
from ..reference.genome_fasta import load_genome_sequence_lengths

__all__ = [
    "CURATED_QUANTIFIED_FILTER",
    "export_datasets",
    "export_conditions",
    "export_samples",
    "export_sample_qc",
    "export_expression",
    "export_classification",
    "export_chromosome_expression",
    "write_all",
]

# Shared gate: a sample counts as "on the site" once it is both pipeline-
# QUANTIFIED and condition-curated. Reused by every export function below so
# datasets/conditions/samples/expression can never disagree about which
# samples exist.
CURATED_QUANTIFIED_FILTER = "s.pipeline_status = 'QUANTIFIED' AND s.condition_id IS NOT NULL"


def _clean_records(df: pd.DataFrame) -> list[dict[str, Any]]:
    """DataFrame -> list[dict], NaN/NaT -> None, numpy scalars -> native Python."""
    return json.loads(df.to_json(orient="records", date_format="iso"))


def _write_json(path: Path, payload: Any) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(payload, separators=(",", ":"), ensure_ascii=False)
    path.write_text(text, encoding="utf-8")
    return len(text.encode("utf-8"))


def export_datasets(conn: duckdb.DuckDBPyConnection) -> list[dict[str, Any]]:
    """Only datasets backing at least one curated+quantified sample."""
    df = conn.execute(
        f"""
        SELECT DISTINCT
            d.dataset_id, d.bioproject, NULLIF(d.geo_accession, '') AS geo_accession,
            NULLIF(d.publication_doi, '') AS publication_doi, d.publication_title,
            d.organism, d.strain, d.study_description, d.source_repository
        FROM datasets d
        JOIN samples s ON s.bioproject = d.bioproject
        WHERE {CURATED_QUANTIFIED_FILTER}
        ORDER BY d.dataset_id
        """
    ).fetchdf()
    return _clean_records(df)


def export_conditions(conn: duckdb.DuckDBPyConnection) -> list[dict[str, Any]]:
    """Only conditions actually referenced by a curated+quantified sample."""
    df = conn.execute(
        f"""
        SELECT DISTINCT
            c.condition_id, c.condition_label, c.strain,
            NULLIF(c.medium, '') AS medium, NULLIF(c.culture_mode, '') AS culture_mode,
            c.carbon_source, c.nitrogen_source, c.substrate,
            c.temperature_C, c.pH, c.time_value, c.time_unit,
            c.stress, c.treatment, c.oxygen_condition, c.developmental_stage
        FROM conditions c
        JOIN samples s ON s.condition_id = c.condition_id
        WHERE {CURATED_QUANTIFIED_FILTER}
        ORDER BY c.condition_id
        """
    ).fetchdf()
    return _clean_records(df)


def _derive_qc_status(duplication_rate: float | None, q30_rate: float | None, assigned_fraction: float | None) -> str:
    """Placeholder pass/warning/fail heuristic.

    The pipeline does not yet compute its own categorical QC verdict
    (Milestone 5/6 scope) -- this is a simple, documented threshold rule
    over the fastp/Salmon metrics actually captured in `sample_qc`, not a
    pipeline-reported status. Revisit once real QC gating exists.
    """
    dup = duplication_rate if duplication_rate is not None and not pd.isna(duplication_rate) else 0.0
    q30 = q30_rate if q30_rate is not None and not pd.isna(q30_rate) else 1.0
    frac = assigned_fraction if assigned_fraction is not None and not pd.isna(assigned_fraction) else 1.0
    if dup > 0.5 or frac < 0.3:
        return "fail"
    if dup > 0.35 or q30 < 0.85 or frac < 0.5:
        return "warning"
    return "pass"


def _fetch_sample_qc_wide(conn: duckdb.DuckDBPyConnection) -> pd.DataFrame:
    """Pivot the EAV `sample_qc` table into one row per sample."""
    long_df = conn.execute(
        f"""
        SELECT q.sample_id, q.metric_name, q.metric_value
        FROM sample_qc q
        JOIN samples s ON s.sample_id = q.sample_id
        WHERE {CURATED_QUANTIFIED_FILTER}
        """
    ).fetchdf()
    if long_df.empty:
        return pd.DataFrame(
            columns=["sample_id", "q30_rate", "duplication_rate", "salmon_total_gene_assigned_counts", "assigned_fraction"]
        )
    wide = long_df.pivot_table(index="sample_id", columns="metric_name", values="metric_value", aggfunc="first")
    out = pd.DataFrame(index=wide.index)
    out["q30_rate"] = wide.get("fastp_q30_rate_after")
    out["duplication_rate"] = wide.get("fastp_duplication_rate")
    out["salmon_total_gene_assigned_counts"] = wide.get("salmon_total_gene_assigned_counts")
    total_reads = wide.get("fastp_total_reads_after")
    # Proxy for mapping/assignment rate: fraction of fastp's post-filter
    # reads Salmon assigned to a gene. Not a pipeline-reported "mapping
    # rate" metric -- Salmon's own mapping-rate statistic isn't captured in
    # sample_qc yet -- but it is a real ratio of two measured quantities,
    # clipped to [0, 1] defensively.
    if total_reads is not None:
        frac = (out["salmon_total_gene_assigned_counts"] / total_reads).clip(upper=1.0)
    else:
        frac = pd.Series(index=out.index, dtype=float)
    out["assigned_fraction"] = frac
    return out.reset_index()


def export_samples(conn: duckdb.DuckDBPyConnection) -> list[dict[str, Any]]:
    df = conn.execute(
        f"""
        SELECT
            s.sample_id, s.run_accession, s.biosample, s.bioproject, s.strain,
            s.condition_id, TRY_CAST(s.biological_replicate AS INTEGER) AS biological_replicate,
            s.library_layout, s.library_strategy, s.read_count,
            s.pipeline_status, s.reference_version, s.pipeline_version
        FROM samples s
        WHERE {CURATED_QUANTIFIED_FILTER}
        ORDER BY s.sample_id
        """
    ).fetchdf()

    genes_detected = conn.execute(
        f"""
        SELECT s.sample_id, COUNT(*) FILTER (WHERE ge.TPM > 0) AS genes_detected
        FROM gene_expression ge
        JOIN samples s ON s.sample_id = ge.sample_id
        WHERE {CURATED_QUANTIFIED_FILTER}
        GROUP BY s.sample_id
        """
    ).fetchdf()

    qc_wide = _fetch_sample_qc_wide(conn)
    df = df.merge(qc_wide, on="sample_id", how="left").merge(genes_detected, on="sample_id", how="left")
    df["qc_status"] = [
        _derive_qc_status(row.duplication_rate, row.q30_rate, row.assigned_fraction) for row in df.itertuples()
    ]
    df = df.drop(columns=["q30_rate", "duplication_rate", "assigned_fraction", "salmon_total_gene_assigned_counts", "genes_detected"], errors="ignore")
    return _clean_records(df)


def export_sample_qc(conn: duckdb.DuckDBPyConnection) -> list[dict[str, Any]]:
    genes_detected = conn.execute(
        f"""
        SELECT s.sample_id, COUNT(*) FILTER (WHERE ge.TPM > 0) AS genes_detected
        FROM gene_expression ge
        JOIN samples s ON s.sample_id = ge.sample_id
        WHERE {CURATED_QUANTIFIED_FILTER}
        GROUP BY s.sample_id
        """
    ).fetchdf()
    qc_wide = _fetch_sample_qc_wide(conn)
    df = qc_wide.merge(genes_detected, on="sample_id", how="left")
    df = df.rename(columns={"assigned_fraction": "mapping_rate"})
    df = df[["sample_id", "mapping_rate", "q30_rate", "duplication_rate", "genes_detected", "salmon_total_gene_assigned_counts"]]
    df["mapping_rate"] = df["mapping_rate"].round(4)
    df["q30_rate"] = df["q30_rate"].round(4)
    df["duplication_rate"] = df["duplication_rate"].round(4)
    return _clean_records(df)


def export_expression(conn: duckdb.DuckDBPyConnection) -> dict[str, Any]:
    """Compact tuple rows (not objects) -- ~374k rows at the current pilot
    scale, so field-name repetition would roughly double the payload."""
    df = conn.execute(
        f"""
        SELECT ge.sample_id, ge.canonical_gene_id, ge.TPM, ge.estimated_counts
        FROM gene_expression ge
        JOIN samples s ON s.sample_id = ge.sample_id
        WHERE {CURATED_QUANTIFIED_FILTER}
        ORDER BY ge.canonical_gene_id, ge.sample_id
        """
    ).fetchdf()
    df["TPM"] = df["TPM"].round(2)
    df["estimated_counts"] = df["estimated_counts"].round(0)
    rows = df.values.tolist()
    for row in rows:
        row[2] = None if pd.isna(row[2]) else float(row[2])
        row[3] = None if pd.isna(row[3]) else int(row[3])
    return {"columns": ["sample_id", "canonical_gene_id", "TPM", "estimated_counts"], "rows": rows}


_CLASSIFICATION_COLUMNS = [
    "canonical_gene_id",
    "median_TPM",
    "n_detected_conditions",
    "n_conditions",
    "Tau_log1p",
    "Tau_raw",
    "prevalence_TPM_1",
    "robust_CV",
    "cluster_base",
    "biological_label",
    "classification_confidence",
]


_CLASSIFICATION_ROUND_COLS = {"median_TPM", "Tau_log1p", "Tau_raw", "prevalence_TPM_1", "robust_CV"}
_CLASSIFICATION_INT_COLS = {"n_detected_conditions", "n_conditions", "cluster_base"}


def export_classification() -> dict[str, Any] | None:
    """None if `atlas cluster genes` has never been run for this database."""
    if not CLASSIFICATION_FILE.is_file():
        return None
    table = pd.read_parquet(CLASSIFICATION_FILE)
    table = table.reset_index().rename(columns={"gene": "canonical_gene_id"})[_CLASSIFICATION_COLUMNS]

    rows: list[list[Any]] = []
    for record in table.to_dict(orient="records"):
        row: list[Any] = []
        for col in _CLASSIFICATION_COLUMNS:
            value = record[col]
            if isinstance(value, float) and math.isnan(value):
                row.append(None)
            elif col in _CLASSIFICATION_ROUND_COLS:
                row.append(round(float(value), 4))
            elif col in _CLASSIFICATION_INT_COLS:
                row.append(int(value))
            elif isinstance(value, (pd.Timestamp,)):
                row.append(str(value))
            else:
                row.append(value)
        rows.append(row)
    return {"columns": _CLASSIFICATION_COLUMNS, "rows": rows}


_CHROMOSOME_BIN_COLUMNS = ["start", "end", "n_genes", "n_detected_genes", "mean_TPM", "log10_mean_TPM"]


def export_chromosome_expression(conn: duckdb.DuckDBPyConnection, bin_size_bp: int = DEFAULT_BIN_SIZE_BP) -> dict[str, Any] | None:
    """Whole-genome expression map: per-chromosome, fixed-size-window mean
    TPM, for the karyotype-style heatmap (TODO.md "chromosome-wide TPM
    abundance map"). None if `atlas stats genes`/`atlas cluster genes`
    hasn't produced a feature table yet, or the genome FASTA evidence file
    isn't on disk -- both are prerequisites, not optional.
    """
    if not GENE_FEATURE_TABLE_FILE.is_file() or not FUNGIDB_GENOME_FASTA_FILE.is_file():
        return None

    genes = conn.execute('SELECT canonical_gene_id, chromosome, start, "end" FROM genes').fetchdf()
    feature_table = pd.read_parquet(GENE_FEATURE_TABLE_FILE)
    median_tpm = feature_table["median_TPM"]
    lengths = chromosome_lengths_by_name(load_genome_sequence_lengths(FUNGIDB_GENOME_FASTA_FILE))

    bins_df = bin_gene_expression(genes, median_tpm, lengths, bin_size_bp=bin_size_bp)

    chromosomes_payload: list[dict[str, Any]] = []
    for chrom in NUCLEAR_CHROMOSOMES:
        chrom_length = lengths.get(chrom)
        if chrom_length is None:
            continue
        chrom_bins = bins_df[bins_df["chromosome"] == chrom].sort_values("bin_index")
        bin_rows = []
        for row in chrom_bins.itertuples(index=False):
            bin_rows.append(
                [
                    int(row.bin_start),
                    int(row.bin_end),
                    int(row.n_genes),
                    int(row.n_detected_genes),
                    None if math.isnan(row.mean_TPM) else round(float(row.mean_TPM), 3),
                    None if math.isnan(row.log10_mean_TPM) else round(float(row.log10_mean_TPM), 4),
                ]
            )
        chromosomes_payload.append({"chromosome": chrom, "length": chrom_length, "bins": bin_rows})

    return {"bin_size_bp": bin_size_bp, "bin_columns": _CHROMOSOME_BIN_COLUMNS, "chromosomes": chromosomes_payload}


def write_all(conn: duckdb.DuckDBPyConnection, out_dir: Path = WEB_DATA_DIR) -> dict[str, Any]:
    """Write every JSON snapshot; returns a summary dict for CLI reporting."""
    summary: dict[str, Any] = {}

    datasets = export_datasets(conn)
    summary["datasets_bytes"] = _write_json(out_dir / "datasets.json", datasets)
    summary["n_datasets"] = len(datasets)

    conditions = export_conditions(conn)
    summary["conditions_bytes"] = _write_json(out_dir / "conditions.json", conditions)
    summary["n_conditions"] = len(conditions)

    samples = export_samples(conn)
    summary["samples_bytes"] = _write_json(out_dir / "samples.json", samples)
    summary["n_samples"] = len(samples)

    sample_qc = export_sample_qc(conn)
    summary["sample_qc_bytes"] = _write_json(out_dir / "sample_qc.json", sample_qc)
    summary["n_sample_qc"] = len(sample_qc)

    expression = export_expression(conn)
    summary["expression_bytes"] = _write_json(out_dir / "expression.json", expression)
    summary["n_expression_rows"] = len(expression["rows"])

    classification = export_classification()
    if classification is not None:
        summary["classification_bytes"] = _write_json(out_dir / "classification.json", classification)
        summary["n_classification_rows"] = len(classification["rows"])
    else:
        summary["classification_bytes"] = 0
        summary["n_classification_rows"] = 0

    chromosome_expression = export_chromosome_expression(conn)
    if chromosome_expression is not None:
        summary["chromosome_expression_bytes"] = _write_json(out_dir / "chromosome_expression.json", chromosome_expression)
        summary["n_chromosome_bins"] = sum(len(c["bins"]) for c in chromosome_expression["chromosomes"])
    else:
        summary["chromosome_expression_bytes"] = 0
        summary["n_chromosome_bins"] = 0

    return summary
