"""Tests for aoryzae_atlas.discovery.parse (spec section 23)."""
from __future__ import annotations

import csv

from aoryzae_atlas.discovery.parse import load_discovered_runs

_COLUMNS = [
    "run_1_accession",
    "experiment_accession",
    "sample_accession",
    "sample_external_id_1",
    "sample_external_id_1_namespace",
    "study_accession",
    "study_external_id_1",
    "study_external_id_1_namespace",
    "sample_scientific_name",
    "sample_title",
    "experiment_title",
    "study_study_title",
    "study_study_abstract",
    "experiment_library_strategy",
    "experiment_library_source",
    "experiment_library_selection",
    "library_layout",
    "experiment_instrument_model",
    "experiment_design_description",
    "run_1_total_spots",
    "run_1_total_bases",
    "run_1_size",
    "run_1_published",
    "sample_attributes_1_tag",
    "sample_attributes_1_value",
    "sample_attributes_2_tag",
    "sample_attributes_2_value",
]


def _write_raw_tsv(tmp_path, rows: list[dict]) -> "Path":
    path = tmp_path / "raw.tsv"
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=_COLUMNS, delimiter="\t")
        writer.writeheader()
        for row in rows:
            writer.writerow({col: row.get(col, "") for col in _COLUMNS})
    return path


def test_resolves_bioproject_and_biosample_from_namespaced_columns(tmp_path):
    path = _write_raw_tsv(
        tmp_path,
        [
            {
                "run_1_accession": "SRR1",
                "sample_accession": "SRS1",
                "sample_external_id_1": "SAMN1",
                "sample_external_id_1_namespace": "BioSample",
                "study_accession": "SRP1",
                "study_external_id_1": "PRJNA1",
                "study_external_id_1_namespace": "BioProject",
                "sample_scientific_name": "Aspergillus oryzae",
                "experiment_library_strategy": "RNA-Seq",
                "experiment_library_source": "TRANSCRIPTOMIC",
                "sample_attributes_1_tag": "strain",
                "sample_attributes_1_value": "RIB40",
            }
        ],
    )
    runs = load_discovered_runs(path)
    assert len(runs) == 1
    run = runs[0]
    assert run.bioproject == "PRJNA1"
    assert run.biosample == "SAMN1"
    assert run.sample_attributes == {"strain": "RIB40"}


def test_falls_back_to_sra_accessions_when_namespace_does_not_match(tmp_path):
    path = _write_raw_tsv(
        tmp_path,
        [
            {
                "run_1_accession": "SRR2",
                "sample_accession": "SRS2",
                "sample_external_id_1": "SOMETHING_ELSE",
                "sample_external_id_1_namespace": "NotBioSample",
                "study_accession": "SRP2",
                "study_external_id_1": "SOMETHING_ELSE_2",
                "study_external_id_1_namespace": "NotBioProject",
                "sample_scientific_name": "Aspergillus oryzae",
            }
        ],
    )
    run = load_discovered_runs(path)[0]
    assert run.bioproject == ""  # never fabricate an unresolvable BioProject
    assert run.biosample == "SRS2"  # falls back to the SRA-native sample accession
