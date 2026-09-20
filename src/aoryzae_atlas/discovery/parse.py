"""Parse pysradb's raw SRA search TSV into normalized per-run records.

pysradb's `--detailed` output is one row per sequencing run, with the
BioProject/BioSample accessions carried as a namespaced pair of columns
(`study_external_id_1` / `study_external_id_1_namespace`, similarly for
sample) rather than a single clean column, and up to 8 free-form
`sample_attributes_<N>_tag`/`_value` pairs whose tags vary per submission
(strain, isolation_source, treatment, collection_date, geo_loc_name, ...).
This module normalizes both into a stable `DiscoveredRun` shape.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

_SAMPLE_ATTR_MAX = 8


def _get(row: pd.Series, column: str) -> str:
    value = row.get(column, "")
    return "" if pd.isna(value) else str(value)


def _external_id(row: pd.Series, id_column: str, namespace_column: str, expected_namespace: str) -> str:
    if _get(row, namespace_column) == expected_namespace:
        return _get(row, id_column)
    return ""


def _sample_attributes(row: pd.Series) -> dict[str, str]:
    attrs: dict[str, str] = {}
    for i in range(1, _SAMPLE_ATTR_MAX + 1):
        tag = _get(row, f"sample_attributes_{i}_tag")
        value = _get(row, f"sample_attributes_{i}_value")
        if tag and value:
            attrs[tag] = value
    return attrs


@dataclass(frozen=True)
class DiscoveredRun:
    run_accession: str
    experiment_accession: str
    sample_accession_sra: str  # SRS...
    biosample: str  # SAMN... when resolvable, else falls back to sample_accession_sra
    study_accession: str  # SRP...
    bioproject: str  # PRJNA... when resolvable
    sample_scientific_name: str
    sample_title: str
    experiment_title: str
    study_title: str
    study_abstract: str
    library_strategy: str
    library_source: str
    library_selection: str
    library_layout: str
    instrument_model: str
    design_description: str
    total_spots: str
    total_bases: str
    run_size_bytes: str
    published_date: str
    sample_attributes: dict[str, str] = field(default_factory=dict)


def load_discovered_runs(raw_tsv_path: Path) -> list[DiscoveredRun]:
    frame = pd.read_csv(raw_tsv_path, sep="\t", dtype=str, keep_default_na=False, low_memory=False)
    runs: list[DiscoveredRun] = []
    for _, row in frame.iterrows():
        biosample = _external_id(row, "sample_external_id_1", "sample_external_id_1_namespace", "BioSample")
        runs.append(
            DiscoveredRun(
                run_accession=_get(row, "run_1_accession"),
                experiment_accession=_get(row, "experiment_accession"),
                sample_accession_sra=_get(row, "sample_accession"),
                biosample=biosample or _get(row, "sample_accession"),
                study_accession=_get(row, "study_accession"),
                bioproject=_external_id(row, "study_external_id_1", "study_external_id_1_namespace", "BioProject"),
                sample_scientific_name=_get(row, "sample_scientific_name"),
                sample_title=_get(row, "sample_title"),
                experiment_title=_get(row, "experiment_title"),
                study_title=_get(row, "study_study_title"),
                study_abstract=_get(row, "study_study_abstract"),
                library_strategy=_get(row, "experiment_library_strategy"),
                library_source=_get(row, "experiment_library_source"),
                library_selection=_get(row, "experiment_library_selection"),
                library_layout=_get(row, "library_layout"),
                instrument_model=_get(row, "experiment_instrument_model"),
                design_description=_get(row, "experiment_design_description"),
                total_spots=_get(row, "run_1_total_spots"),
                total_bases=_get(row, "run_1_total_bases"),
                run_size_bytes=_get(row, "run_1_size"),
                published_date=_get(row, "run_1_published"),
                sample_attributes=_sample_attributes(row),
            )
        )
    return runs
