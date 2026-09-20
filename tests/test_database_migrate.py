"""Tests for aoryzae_atlas.database.migrate (spec section 8, Milestone 4)."""
from __future__ import annotations

import duckdb

from aoryzae_atlas.database.migrate import apply_migrations


def _write_migration(migrations_dir, name, sql):
    (migrations_dir / name).write_text(sql, encoding="utf-8")


def test_apply_migrations_creates_tables_and_tracks_them(tmp_path):
    migrations_dir = tmp_path / "migrations"
    migrations_dir.mkdir()
    _write_migration(migrations_dir, "0001_a.sql", "CREATE TABLE a (x INT);")
    _write_migration(migrations_dir, "0002_b.sql", "CREATE TABLE b (y INT);")

    db_path = tmp_path / "test.duckdb"
    applied = apply_migrations(db_path, migrations_dir)
    assert applied == ["0001_a.sql", "0002_b.sql"]

    conn = duckdb.connect(str(db_path))
    try:
        conn.execute("INSERT INTO a VALUES (1)")
        conn.execute("INSERT INTO b VALUES (2)")
        assert conn.execute("SELECT filename FROM _schema_migrations ORDER BY filename").fetchall() == [
            ("0001_a.sql",),
            ("0002_b.sql",),
        ]
    finally:
        conn.close()


def test_apply_migrations_is_idempotent(tmp_path):
    migrations_dir = tmp_path / "migrations"
    migrations_dir.mkdir()
    _write_migration(migrations_dir, "0001_a.sql", "CREATE TABLE a (x INT);")

    db_path = tmp_path / "test.duckdb"
    first = apply_migrations(db_path, migrations_dir)
    second = apply_migrations(db_path, migrations_dir)
    assert first == ["0001_a.sql"]
    assert second == []


def test_apply_migrations_only_applies_new_files(tmp_path):
    migrations_dir = tmp_path / "migrations"
    migrations_dir.mkdir()
    _write_migration(migrations_dir, "0001_a.sql", "CREATE TABLE a (x INT);")

    db_path = tmp_path / "test.duckdb"
    apply_migrations(db_path, migrations_dir)

    _write_migration(migrations_dir, "0002_b.sql", "CREATE TABLE b (y INT);")
    second = apply_migrations(db_path, migrations_dir)
    assert second == ["0002_b.sql"]
