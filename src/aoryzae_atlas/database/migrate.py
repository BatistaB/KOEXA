"""Minimal forward-only SQL migration runner for atlas.duckdb.

Migrations are numbered .sql files under database/migrations/, applied in
filename order, each exactly once, tracked in `_schema_migrations`. There
is no down-migration support -- at this stage a wrong migration is fixed
by adding a new corrective one, not by rewriting/removing an applied file
(spec section 36: data/schema history should be append-only where
practical).
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import duckdb

MIGRATIONS_DIR = Path(__file__).parent / "migrations"

_TRACKING_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS _schema_migrations (
    filename TEXT PRIMARY KEY,
    applied_at TIMESTAMP
)
"""


def list_migration_files(migrations_dir: Path = MIGRATIONS_DIR) -> list[Path]:
    return sorted(migrations_dir.glob("*.sql"))


def applied_migrations(conn: duckdb.DuckDBPyConnection) -> set[str]:
    conn.execute(_TRACKING_TABLE_SQL)
    rows = conn.execute("SELECT filename FROM _schema_migrations").fetchall()
    return {row[0] for row in rows}


def apply_migrations(db_path: Path, migrations_dir: Path = MIGRATIONS_DIR) -> list[str]:
    """Apply any not-yet-applied migration files. Returns the filenames applied this run."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = duckdb.connect(str(db_path))
    try:
        already_applied = applied_migrations(conn)
        newly_applied: list[str] = []
        for migration_file in list_migration_files(migrations_dir):
            if migration_file.name in already_applied:
                continue
            sql = migration_file.read_text(encoding="utf-8")
            conn.execute(sql)
            conn.execute(
                "INSERT INTO _schema_migrations (filename, applied_at) VALUES (?, ?)",
                [migration_file.name, datetime.now(timezone.utc)],
            )
            newly_applied.append(migration_file.name)
        return newly_applied
    finally:
        conn.close()
