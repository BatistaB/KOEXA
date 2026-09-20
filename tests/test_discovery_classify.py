"""Tests for aoryzae_atlas.discovery.classify (spec section 23)."""
from __future__ import annotations

from aoryzae_atlas.discovery.classify import build_discovery_tables
from aoryzae_atlas.discovery.parse import DiscoveredRun


def _run(**overrides) -> DiscoveredRun:
    defaults = dict(
        run_accession="SRR1",
        experiment_accession="SRX1",
        sample_accession_sra="SRS1",
        biosample="SAMN1",
        study_accession="SRP1",
        bioproject="PRJNA1",
        sample_scientific_name="Aspergillus oryzae",
        sample_title="control sample",
        experiment_title="exp",
        study_title="study",
        study_abstract="abstract",
        library_strategy="RNA-Seq",
        library_source="TRANSCRIPTOMIC",
        library_selection="cDNA",
        library_layout="PAIRED",
        instrument_model="Illumina",
        design_description="",
        total_spots="1000",
        total_bases="200000",
        run_size_bytes="1000000",
        published_date="2026-01-01",
        sample_attributes={"strain": "RIB40"},
    )
    defaults.update(overrides)
    return DiscoveredRun(**defaults)


def test_passing_run_is_requires_review_not_recommended():
    tables = build_discovery_tables([_run()], discovery_date="2026-09-20")
    assert len(tables.runs) == 1
    assert tables.runs[0].status == "REQUIRES_REVIEW"
    assert tables.exclusions == []


def test_wrong_strategy_is_excluded_with_reason():
    tables = build_discovery_tables([_run(library_strategy="WGS")], discovery_date="2026-09-20")
    assert tables.runs[0].status == "EXCLUDE"
    assert "WGS" in tables.runs[0].reason
    assert len(tables.exclusions) == 1
    assert tables.exclusions[0].level == "run"


def test_organism_mismatch_is_excluded():
    tables = build_discovery_tables(
        [_run(sample_scientific_name="Aspergillus flavus")], discovery_date="2026-09-20"
    )
    assert tables.runs[0].status == "EXCLUDE"
    assert "oryzae" in tables.runs[0].reason


def test_missing_run_accession_is_excluded():
    tables = build_discovery_tables([_run(run_accession="")], discovery_date="2026-09-20")
    assert tables.runs[0].status == "EXCLUDE"
    assert "no run accession" in tables.runs[0].reason


def test_multiple_runs_aggregate_into_one_sample_and_one_study():
    runs = [_run(run_accession="SRR1"), _run(run_accession="SRR2")]
    tables = build_discovery_tables(runs, discovery_date="2026-09-20")
    assert len(tables.runs) == 2
    assert len(tables.samples) == 1
    assert tables.samples[0].run_count == 2
    assert tables.samples[0].strain == "RIB40"
    assert len(tables.studies) == 1
    assert tables.studies[0].bioproject == "PRJNA1"


def test_sample_excluded_only_when_all_its_runs_are_excluded():
    runs = [_run(run_accession="SRR1"), _run(run_accession="SRR2", library_strategy="WGS")]
    tables = build_discovery_tables(runs, discovery_date="2026-09-20")
    assert tables.samples[0].status == "REQUIRES_REVIEW"

    all_bad = [_run(run_accession="SRR1", library_strategy="WGS"), _run(run_accession="SRR2", library_strategy="WGS")]
    tables_bad = build_discovery_tables(all_bad, discovery_date="2026-09-20")
    assert tables_bad.samples[0].status == "EXCLUDE"


def test_study_without_resolvable_bioproject_keeps_it_blank():
    tables = build_discovery_tables([_run(bioproject="")], discovery_date="2026-09-20")
    assert tables.studies[0].bioproject == ""
    assert tables.studies[0].dataset_id == "STUDY:SRP1"
