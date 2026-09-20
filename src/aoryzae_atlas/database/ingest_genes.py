"""Load metadata/gene_master.tsv and gene_external_identifiers.tsv into DuckDB.

Both source TSVs are fully derived, deterministic Milestone 1/3 outputs
(no manual curation lives only in the database for these two tables), so
each run truncates and reloads rather than upserting -- simplest way to
stay safe to re-run without drift between the TSVs and the database.
"""
from __future__ import annotations

from pathlib import Path

import duckdb
import pandas as pd


def load_genes(conn: duckdb.DuckDBPyConnection, gene_master_tsv: Path) -> int:
    frame = pd.read_csv(gene_master_tsv, sep="\t", dtype=str, keep_default_na=False)
    frame["start"] = pd.to_numeric(frame["start"], errors="coerce")
    frame["end"] = pd.to_numeric(frame["end"], errors="coerce")
    conn.execute("DELETE FROM genes")
    conn.register("genes_frame", frame)
    conn.execute(
        """
        INSERT INTO genes
        SELECT canonical_gene_id, gene_symbol, gene_name, chromosome, start, "end",
               strand, biotype, description, reference_version
        FROM genes_frame
        """
    )
    conn.unregister("genes_frame")
    return len(frame)


def load_gene_external_identifiers(conn: duckdb.DuckDBPyConnection, path: Path) -> int:
    frame = pd.read_csv(path, sep="\t", dtype=str, keep_default_na=False)
    conn.execute("DELETE FROM gene_external_identifiers")
    conn.register("gxi_frame", frame)
    conn.execute(
        """
        INSERT INTO gene_external_identifiers
        SELECT canonical_gene_id, namespace, external_id, external_name, mapping_type,
               mapping_confidence, mapping_method, evidence, source_file, source_version,
               source_checksum, reference_version
        FROM gxi_frame
        """
    )
    conn.unregister("gxi_frame")
    return len(frame)
