"""Tests for aoryzae_atlas.discovery.crossref (spec section 23)."""
from __future__ import annotations

from aoryzae_atlas.discovery.classify import StudyRow
from aoryzae_atlas.discovery.crossref import StudyCrossref, apply_crossrefs_to_studies


def _study(**overrides) -> StudyRow:
    defaults = dict(
        dataset_id="PRJNA1",
        bioproject="PRJNA1",
        study_accession="SRP1",
        geo_accession="",
        publication_doi="",
        publication_title="",
        organism="Aspergillus oryzae",
        strain="RIB40",
        study_description="desc",
        source_repository="NCBI SRA",
        discovery_date="2026-09-20",
        metadata_status="discovered",
        notes="1 biosample(s), 1 run(s)",
    )
    defaults.update(overrides)
    return StudyRow(**defaults)


def test_apply_crossrefs_fills_geo_accession_and_notes_pmid():
    studies = [_study()]
    crossrefs = {"SRP1": StudyCrossref(study_accession="SRP1", geo_accession="GSE123", pmid="99999")}
    updated = apply_crossrefs_to_studies(studies, crossrefs)
    assert updated[0].geo_accession == "GSE123"
    assert "PMID:99999" in updated[0].notes
    # DOI/title are never guessed just because a PMID was found.
    assert updated[0].publication_doi == ""
    assert updated[0].publication_title == ""


def test_apply_crossrefs_leaves_study_unchanged_when_no_match():
    studies = [_study()]
    updated = apply_crossrefs_to_studies(studies, {})
    assert updated[0] == studies[0]


def test_apply_crossrefs_no_pmid_does_not_touch_notes():
    studies = [_study()]
    crossrefs = {"SRP1": StudyCrossref(study_accession="SRP1", geo_accession="", pmid="")}
    updated = apply_crossrefs_to_studies(studies, crossrefs)
    assert updated[0].notes == studies[0].notes
    assert updated[0].geo_accession == ""
