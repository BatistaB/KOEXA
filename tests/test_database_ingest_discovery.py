"""Tests for aoryzae_atlas.database.ingest_discovery (spec section 23, Milestone 4)."""
from __future__ import annotations

import duckdb
import pytest

from aoryzae_atlas.database.ingest_discovery import load_datasets, load_samples
from aoryzae_atlas.database.migrate import apply_migrations

STUDIES_HEADER = (
    "dataset_id\tbioproject\tstudy_accession\tgeo_accession\tpublication_doi\t"
    "publication_title\torganism\tstrain\tstudy_description\tsource_repository\t"
    "discovery_date\tmetadata_status\tnotes\n"
)
RUNS_HEADER = (
    "run_accession\texperiment_accession\tbiosample\tbioproject\tstudy_accession\t"
    "library_strategy\tlibrary_source\tlibrary_selection\tlibrary_layout\t"
    "instrument_model\ttotal_spots\ttotal_bases\trun_size_bytes\tpublished_date\t"
    "status\treason\n"
)
SAMPLES_HEADER = (
    "biosample\tbioproject\tstudy_accession\tsample_scientific_name\tsample_title\t"
    "strain\tcondition_clues\tlibrary_layout\tlibrary_strategy\tlibrary_source\t"
    "run_count\tstatus\treason\n"
)


@pytest.fixture
def conn(tmp_path):
    db_path = tmp_path / "test.duckdb"
    apply_migrations(db_path)
    connection = duckdb.connect(str(db_path))
    yield connection
    connection.close()


def test_load_datasets(tmp_path, conn):
    path = tmp_path / "studies.tsv"
    path.write_text(
        STUDIES_HEADER + "PRJNA1\tPRJNA1\tSRP1\t\t\t\tAspergillus oryzae\tRIB40\tdesc\tNCBI SRA\t2026-09-20\tdiscovered\tnote\n",
        encoding="utf-8",
    )
    n = load_datasets(conn, path)
    assert n == 1
    row = conn.execute("SELECT dataset_id, bioproject, organism FROM datasets").fetchone()
    assert row == ("PRJNA1", "PRJNA1", "Aspergillus oryzae")


def test_load_samples_maps_status_to_sample_state(tmp_path, conn):
    runs_path = tmp_path / "runs.tsv"
    runs_path.write_text(
        RUNS_HEADER
        + "SRR1\tSRX1\tSAMN1\tPRJNA1\tSRP1\tRNA-Seq\tTRANSCRIPTOMIC\tcDNA\tPAIRED\tIllumina\t1000\t200000\t1000000\t2026-01-01\tREQUIRES_REVIEW\t\n"
        + "SRR2\tSRX2\tSAMN2\tPRJNA1\tSRP1\tWGS\tGENOMIC\tcDNA\tPAIRED\tIllumina\t1000\t200000\t1000000\t2026-01-01\tEXCLUDE\tnot RNA-Seq\n",
        encoding="utf-8",
    )
    samples_path = tmp_path / "samples.tsv"
    samples_path.write_text(
        SAMPLES_HEADER
        + "SAMN1\tPRJNA1\tSRP1\tAspergillus oryzae\ttitle\tRIB40\t\tPAIRED\tRNA-Seq\tTRANSCRIPTOMIC\t1\tREQUIRES_REVIEW\treason\n"
        + "SAMN2\tPRJNA1\tSRP1\tAspergillus oryzae\ttitle\t\t\tPAIRED\tWGS\tGENOMIC\t1\tEXCLUDE\treason\n",
        encoding="utf-8",
    )
    n = load_samples(conn, runs_path, samples_path)
    assert n == 2
    rows = dict(conn.execute("SELECT sample_id, pipeline_status FROM samples").fetchall())
    assert rows["SRR1"] == "METADATA_REVIEW"
    assert rows["SRR2"] == "EXCLUDED"

    exclusion = conn.execute("SELECT exclusion_reason FROM samples WHERE sample_id = 'SRR2'").fetchone()[0]
    assert exclusion == "not RNA-Seq"
    no_exclusion = conn.execute("SELECT exclusion_reason FROM samples WHERE sample_id = 'SRR1'").fetchone()[0]
    assert no_exclusion == ""

    strain = conn.execute("SELECT strain FROM samples WHERE sample_id = 'SRR1'").fetchone()[0]
    assert strain == "RIB40"


def test_reloading_samples_never_resets_pipeline_progress(tmp_path, conn):
    runs_path = tmp_path / "runs.tsv"
    runs_path.write_text(
        RUNS_HEADER
        + "SRR1\tSRX1\tSAMN1\tPRJNA1\tSRP1\tRNA-Seq\tTRANSCRIPTOMIC\tcDNA\tPAIRED\tIllumina\t1000\t200000\t1000000\t2026-01-01\tREQUIRES_REVIEW\t\n",
        encoding="utf-8",
    )
    samples_path = tmp_path / "samples.tsv"
    samples_path.write_text(
        SAMPLES_HEADER + "SAMN1\tPRJNA1\tSRP1\tAspergillus oryzae\ttitle\tRIB40\t\tPAIRED\tRNA-Seq\tTRANSCRIPTOMIC\t1\tREQUIRES_REVIEW\treason\n",
        encoding="utf-8",
    )
    load_samples(conn, runs_path, samples_path)

    # Simulate real pipeline progress made after discovery.
    conn.execute("UPDATE samples SET pipeline_status = 'QUANTIFIED' WHERE sample_id = 'SRR1'")

    # Re-running discovery ingestion (e.g. a periodic re-discovery) must not
    # reset that progress back to METADATA_REVIEW.
    load_samples(conn, runs_path, samples_path)
    status = conn.execute("SELECT pipeline_status FROM samples WHERE sample_id = 'SRR1'").fetchone()[0]
    assert status == "QUANTIFIED"


# --- study groups (aoryzae_atlas.database.study_groups) -----------------------

def _group_fixture(tmp_path):
    studies = tmp_path / "studies.tsv"
    studies.write_text(
        STUDIES_HEADER
        + "PRJNA10\tPRJNA10\tSRP10\t\t\t\tAspergillus oryzae\tRIB40\tProfiling - 4.1.2.1 transcriptome\tNCBI SRA\t2026-09-20\tdiscovered\t\n"
        + "PRJNA11\tPRJNA11\tSRP11\t\t\t\tAspergillus oryzae\tRIB40\tProfiling - 4.1.2.2 transcriptome\tNCBI SRA\t2026-09-21\tdiscovered\t\n"
        + "PRJNA99\tPRJNA99\tSRP99\t\t\t\tAspergillus oryzae\tRIB40\tOther study\tNCBI SRA\t2026-09-20\tdiscovered\t\n",
        encoding="utf-8",
    )
    runs = tmp_path / "runs.tsv"
    runs.write_text(
        RUNS_HEADER
        + "SRR10\tSRX10\tSAMN10\tPRJNA10\tSRP10\tRNA-Seq\tTRANSCRIPTOMIC\tcDNA\tPAIRED\tIllumina\t1000\t200000\t1000000\t2026-01-01\tREQUIRES_REVIEW\t\n"
        + "SRR11\tSRX11\tSAMN11\tPRJNA11\tSRP11\tRNA-Seq\tTRANSCRIPTOMIC\tcDNA\tPAIRED\tIllumina\t1000\t200000\t1000000\t2026-01-01\tREQUIRES_REVIEW\t\n"
        + "SRR99\tSRX99\tSAMN99\tPRJNA99\tSRP99\tRNA-Seq\tTRANSCRIPTOMIC\tcDNA\tPAIRED\tIllumina\t1000\t200000\t1000000\t2026-01-01\tREQUIRES_REVIEW\t\n",
        encoding="utf-8",
    )
    samples = tmp_path / "samples.tsv"
    samples.write_text(SAMPLES_HEADER, encoding="utf-8")
    return studies, runs, samples


def test_load_samples_applies_study_group_and_keeps_source_bioproject(tmp_path, conn):
    _, runs, samples = _group_fixture(tmp_path)
    load_samples(conn, runs, samples, {"PRJNA10": "GRP-A", "PRJNA11": "GRP-A"})
    rows = {r[0]: r[1:] for r in conn.execute("SELECT sample_id, bioproject, source_bioproject FROM samples").fetchall()}
    assert rows["SRR10"] == ("GRP-A", "PRJNA10")
    assert rows["SRR11"] == ("GRP-A", "PRJNA11")
    assert rows["SRR99"] == ("PRJNA99", "PRJNA99")


def test_load_datasets_collapses_members_into_one_row_and_drops_stale_member_rows(tmp_path, conn):
    studies, _, _ = _group_fixture(tmp_path)
    load_datasets(conn, studies)  # first load, before the group exists
    assert conn.execute("SELECT COUNT(*) FROM datasets").fetchone()[0] == 3

    load_datasets(conn, studies, {"PRJNA10": "GRP-A", "PRJNA11": "GRP-A"})
    rows = {r[0]: r for r in conn.execute("SELECT dataset_id, bioproject, study_description, notes, discovery_date FROM datasets").fetchall()}
    assert set(rows) == {"GRP-A", "PRJNA99"}
    assert rows["GRP-A"][1] == "GRP-A"
    assert rows["GRP-A"][2] == "Profiling (2 BioProjects grouped as one study)"
    assert "PRJNA10" in rows["GRP-A"][3] and "PRJNA11" in rows["GRP-A"][3]
    assert str(rows["GRP-A"][4]).startswith("2026-09-20")


def test_load_study_groups_reads_validates_and_tolerates_missing_file(tmp_path):
    from aoryzae_atlas.database.study_groups import load_study_groups

    assert load_study_groups(tmp_path / "missing.tsv") == {}
    ok = tmp_path / "ok.tsv"
    ok.write_text("bioproject\tstudy_id\nPRJNA1\tGRP-A\nPRJNA2\tGRP-A\n", encoding="utf-8")
    assert load_study_groups(ok) == {"PRJNA1": "GRP-A", "PRJNA2": "GRP-A"}

    dup = tmp_path / "dup.tsv"
    dup.write_text("bioproject\tstudy_id\nPRJNA1\tGRP-A\nPRJNA1\tGRP-B\n", encoding="utf-8")
    with pytest.raises(ValueError, match="more than once"):
        load_study_groups(dup)

    clash = tmp_path / "clash.tsv"
    clash.write_text("bioproject\tstudy_id\nPRJNA1\tPRJNA1\n", encoding="utf-8")
    with pytest.raises(ValueError, match="equals a member"):
        load_study_groups(clash)

    bad = tmp_path / "bad.tsv"
    bad.write_text("bioproject\tstudy_id\nPRJNA1\t1 bad id\n", encoding="utf-8")
    with pytest.raises(ValueError, match="must start with a letter"):
        load_study_groups(bad)
