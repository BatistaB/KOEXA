"""Build the studies/samples/runs/exclusions discovery tables (section 23).

Classification here is deliberately conservative: a run only reaches
"EXCLUDE" for an objective, checkable reason (wrong organism/strategy/
source, or no resolvable run accession). Everything else is
"REQUIRES_REVIEW", never "RECOMMENDED_MVP" -- PROJECT_MASTER_SPEC.md
section 23 says to "manually approve a small representative set" aiming
for condition diversity (submerged/solid-state, carbon sources, stress,
growth phase, strain), which is a curation judgment call this code has no
basis to make on its own (AGENTS.md: ask the user rather than guess a
biological/irreversible decision).
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .parse import DiscoveredRun

_CONDITION_CLUE_TAGS = (
    "strain",
    "isolate",
    "genotype",
    "treatment",
    "isolation_source",
    "source_name",
    "collection_date",
    "geo_loc_name",
    "host_description",
    "culture_collection",
)


@dataclass(frozen=True)
class RunRow:
    run_accession: str
    experiment_accession: str
    biosample: str
    bioproject: str
    study_accession: str
    library_strategy: str
    library_source: str
    library_selection: str
    library_layout: str
    instrument_model: str
    total_spots: str
    total_bases: str
    run_size_bytes: str
    published_date: str
    status: str
    reason: str


@dataclass(frozen=True)
class SampleRow:
    biosample: str
    bioproject: str
    study_accession: str
    sample_scientific_name: str
    sample_title: str
    strain: str
    condition_clues: str
    library_layout: str
    library_strategy: str
    library_source: str
    run_count: int
    status: str
    reason: str


@dataclass(frozen=True)
class StudyRow:
    dataset_id: str
    bioproject: str
    geo_accession: str
    publication_doi: str
    publication_title: str
    organism: str
    strain: str
    study_description: str
    source_repository: str
    discovery_date: str
    metadata_status: str
    notes: str


@dataclass(frozen=True)
class ExclusionRow:
    level: str
    accession: str
    bioproject: str
    study_accession: str
    reason: str


@dataclass(frozen=True)
class DiscoveryTables:
    studies: list[StudyRow]
    samples: list[SampleRow]
    runs: list[RunRow]
    exclusions: list[ExclusionRow]


def _classify_run(run: DiscoveredRun) -> tuple[str, str]:
    reasons: list[str] = []
    if run.library_strategy != "RNA-Seq":
        reasons.append(f"library_strategy={run.library_strategy!r} is not RNA-Seq")
    if run.library_source != "TRANSCRIPTOMIC":
        reasons.append(f"library_source={run.library_source!r} is not TRANSCRIPTOMIC")
    if "oryzae" not in run.sample_scientific_name.lower():
        reasons.append(f"sample_scientific_name={run.sample_scientific_name!r} does not mention oryzae")
    if not run.run_accession:
        reasons.append("no run accession resolved")

    if reasons:
        return "EXCLUDE", "; ".join(reasons)
    return (
        "REQUIRES_REVIEW",
        "Passed organism/strategy/source checks; needs human review for condition "
        "diversity and RIB40 compatibility (spec section 23) before approval.",
    )


def _condition_clues(run: DiscoveredRun) -> str:
    parts = [f"{tag}={run.sample_attributes[tag]}" for tag in _CONDITION_CLUE_TAGS if tag in run.sample_attributes]
    # Preserve any remaining tags not in the known list too, so nothing is lost.
    for tag, value in run.sample_attributes.items():
        if tag not in _CONDITION_CLUE_TAGS:
            parts.append(f"{tag}={value}")
    return "; ".join(parts)


def build_discovery_tables(runs: list[DiscoveredRun], discovery_date: str) -> DiscoveryTables:
    run_rows: list[RunRow] = []
    exclusions: list[ExclusionRow] = []
    runs_by_biosample: dict[str, list[DiscoveredRun]] = {}
    runs_by_study_key: dict[str, list[DiscoveredRun]] = {}

    for run in runs:
        status, reason = _classify_run(run)
        run_rows.append(
            RunRow(
                run_accession=run.run_accession,
                experiment_accession=run.experiment_accession,
                biosample=run.biosample,
                bioproject=run.bioproject,
                study_accession=run.study_accession,
                library_strategy=run.library_strategy,
                library_source=run.library_source,
                library_selection=run.library_selection,
                library_layout=run.library_layout,
                instrument_model=run.instrument_model,
                total_spots=run.total_spots,
                total_bases=run.total_bases,
                run_size_bytes=run.run_size_bytes,
                published_date=run.published_date,
                status=status,
                reason=reason,
            )
        )
        if status == "EXCLUDE":
            exclusions.append(
                ExclusionRow(
                    level="run",
                    accession=run.run_accession or run.experiment_accession or "(unresolved)",
                    bioproject=run.bioproject,
                    study_accession=run.study_accession,
                    reason=reason,
                )
            )
        runs_by_biosample.setdefault(run.biosample, []).append(run)
        study_key = run.bioproject or f"STUDY:{run.study_accession}"
        runs_by_study_key.setdefault(study_key, []).append(run)

    sample_rows: list[SampleRow] = []
    for biosample, sample_runs in runs_by_biosample.items():
        statuses = {_classify_run(r)[0] for r in sample_runs}
        sample_status = "EXCLUDE" if statuses == {"EXCLUDE"} else "REQUIRES_REVIEW"
        first = sample_runs[0]
        strain = first.sample_attributes.get("strain") or first.sample_attributes.get("isolate") or ""
        reason = (
            "All runs for this sample failed basic checks; see exclusions.tsv."
            if sample_status == "EXCLUDE"
            else f"{len(sample_runs)} run(s); needs human review (see runs.tsv for any per-run exclusions)."
        )
        sample_rows.append(
            SampleRow(
                biosample=biosample,
                bioproject=first.bioproject,
                study_accession=first.study_accession,
                sample_scientific_name=first.sample_scientific_name,
                sample_title=first.sample_title,
                strain=strain,
                condition_clues=_condition_clues(first),
                library_layout=first.library_layout,
                library_strategy=first.library_strategy,
                library_source=first.library_source,
                run_count=len(sample_runs),
                status=sample_status,
                reason=reason,
            )
        )

    study_rows: list[StudyRow] = []
    for study_key, study_runs in runs_by_study_key.items():
        first = study_runs[0]
        strains = sorted({r.sample_attributes.get("strain", "") for r in study_runs if r.sample_attributes.get("strain")})
        biosamples = {r.biosample for r in study_runs}
        study_rows.append(
            StudyRow(
                dataset_id=study_key,
                bioproject=first.bioproject,
                geo_accession="",  # not resolved in this pass -- see TODO.md
                publication_doi="",  # not resolved in this pass -- see TODO.md
                publication_title="",  # not resolved in this pass -- see TODO.md
                organism=first.sample_scientific_name,
                strain=", ".join(strains),
                study_description=first.study_title or first.study_abstract[:300],
                source_repository="NCBI SRA",
                discovery_date=discovery_date,
                metadata_status="discovered",
                notes=f"{len(biosamples)} biosample(s), {len(study_runs)} run(s) (study_accession={first.study_accession})",
            )
        )

    return DiscoveryTables(studies=study_rows, samples=sample_rows, runs=run_rows, exclusions=exclusions)
