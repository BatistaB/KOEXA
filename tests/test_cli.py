"""Smoke tests for the `atlas` CLI skeleton (spec section 25)."""
from __future__ import annotations

from click.testing import CliRunner

from aoryzae_atlas.cli.main import cli


def test_doctor_exits_zero_on_healthy_repo():
    runner = CliRunner()
    result = runner.invoke(cli, ["doctor"])
    assert result.exit_code == 0, result.output
    assert "AOED doctor report" in result.output


def test_init_is_idempotent():
    runner = CliRunner()
    first = runner.invoke(cli, ["init"])
    assert first.exit_code == 0, first.output
    second = runner.invoke(cli, ["init"])
    assert second.exit_code == 0, second.output


def test_status_runs_without_a_database():
    runner = CliRunner()
    result = runner.invoke(cli, ["status"])
    assert result.exit_code == 0, result.output
    assert "Disk free" in result.output


def test_storage_status_runs():
    runner = CliRunner()
    result = runner.invoke(cli, ["storage", "status"])
    assert result.exit_code == 0, result.output


def test_unimplemented_stub_fails_clearly():
    runner = CliRunner()
    result = runner.invoke(cli, ["dataset", "discover"])
    assert result.exit_code != 0
    assert "not implemented yet" in result.output
    assert "Milestone 2" in result.output


def test_help_lists_all_top_level_command_groups():
    runner = CliRunner()
    result = runner.invoke(cli, ["--help"])
    assert result.exit_code == 0
    for name in ["dataset", "sample", "process", "storage", "qc", "matrix", "stats", "entropy", "cluster", "rank", "coexpr", "report"]:
        assert name in result.output


def test_coexpr_build_on_an_empty_database_fails_clearly_so_refresh_can_skip_it(tmp_path, monkeypatch):
    import duckdb

    from aoryzae_atlas.cli import main as cli_main
    from aoryzae_atlas.database.migrate import apply_migrations

    db_path = tmp_path / "empty.duckdb"
    apply_migrations(db_path)
    monkeypatch.setattr(cli_main, "DATABASE_FILE", db_path)
    result = CliRunner().invoke(cli, ["coexpr", "build"])
    assert result.exit_code != 0 and "QUANTIFIED" in result.output     # a ClickException: 'atlas refresh' reports it as SKIPPED
    assert not isinstance(result.exception, (duckdb.Error, KeyError))


def test_coexpr_query_without_a_build_fails_clearly(tmp_path, monkeypatch):
    from aoryzae_atlas.cli import main as cli_main
    from aoryzae_atlas.database.migrate import apply_migrations

    db_path = tmp_path / "empty.duckdb"
    apply_migrations(db_path)
    monkeypatch.setattr(cli_main, "DATABASE_FILE", db_path)
    result = CliRunner().invoke(cli, ["coexpr", "query", "NOPE"])
    assert result.exit_code != 0 and "Unknown gene" in result.output
