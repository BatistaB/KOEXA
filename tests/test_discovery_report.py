"""Tests for aoryzae_atlas.discovery.report (spec section 23)."""
from __future__ import annotations

from aoryzae_atlas.discovery.classify import build_discovery_tables
from aoryzae_atlas.discovery.parse import DiscoveredRun
from aoryzae_atlas.discovery.report import render_markdown_report, write_discovery_tsvs
from aoryzae_atlas.discovery.sra_search import SearchProvenance


def _run() -> DiscoveredRun:
    return DiscoveredRun(
        run_accession="SRR1",
        experiment_accession="SRX1",
        sample_accession_sra="SRS1",
        biosample="SAMN1",
        study_accession="SRP1",
        bioproject="PRJNA1",
        sample_scientific_name="Aspergillus oryzae",
        sample_title="control",
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


def _provenance() -> SearchProvenance:
    return SearchProvenance(
        tool="pysradb",
        tool_version="2.5.1",
        query_date_utc="2026-09-20T12:00:00+00:00",
        organism="Aspergillus oryzae",
        strategy="RNA-Seq",
        source_db="sra",
        max_results=5000,
        n_rows_returned=1,
        command="pysradb search ...",
    )


def test_write_discovery_tsvs_creates_all_four_files_with_headers(tmp_path):
    tables = build_discovery_tables([_run()], discovery_date="2026-09-20")
    paths = write_discovery_tsvs(tables, tmp_path)
    assert set(paths) == {"studies", "samples", "runs", "exclusions"}
    studies_text = paths["studies"].read_text(encoding="utf-8")
    assert studies_text.startswith("dataset_id\t")
    assert "PRJNA1" in studies_text
    # No exclusions for this all-passing run: header-only or empty is fine either way.
    assert paths["exclusions"].exists()


def test_render_markdown_report_includes_provenance_and_counts():
    tables = build_discovery_tables([_run()], discovery_date="2026-09-20")
    report = render_markdown_report(tables, _provenance())
    assert "pysradb 2.5.1" in report
    assert "Aspergillus oryzae" in report
    assert "REQUIRES_REVIEW: 1" in report
    assert "No FASTQ" not in report  # sanity: don't assert text we didn't write
    assert "no FASTQ/SRA data has been" in report
    assert "--enrich-crossrefs" in report  # not enriched: should point at the flag


def test_render_markdown_report_reflects_crossref_enrichment():
    tables = build_discovery_tables([_run()], discovery_date="2026-09-20")
    report = render_markdown_report(tables, _provenance(), crossrefs_enriched=True)
    assert "were resolved for all 1 studies" in report
    assert "--enrich-crossrefs" not in report  # already enriched: don't tell the user to re-run it
