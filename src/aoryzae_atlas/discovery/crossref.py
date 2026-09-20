"""Best-effort GEO/PMID cross-reference enrichment for discovered studies.

A separate, opt-in follow-up pass (`atlas discovery enrich-crossrefs`)
rather than part of `atlas discovery report`: pysradb's underlying
`sra_metadata()` fetch for PMID resolution takes tens of seconds even when
batched across every study in one call (still far cheaper than one call
per study, which is why this always batches).

DOI/publication title are not resolved here even when a PMID is found --
that needs a further PMID -> article-metadata hop, and is left as an
explicitly unresolved follow-up rather than guessed.
"""
from __future__ import annotations

from dataclasses import dataclass, replace

import pandas as pd
from pysradb.sraweb import SRAweb

from .classify import StudyRow


@dataclass(frozen=True)
class StudyCrossref:
    study_accession: str
    geo_accession: str
    pmid: str


def fetch_study_crossrefs(study_accessions: list[str]) -> dict[str, StudyCrossref]:
    db = SRAweb()
    gse_df = db.srp_to_gse(study_accessions)
    pmid_df = db.srp_to_pmid(study_accessions)

    geo_by_study: dict[str, str] = {}
    for _, row in gse_df.iterrows():
        value = row.get("study_alias")
        if pd.notna(value):
            geo_by_study[row["study_accession"]] = str(value)

    pmid_by_study: dict[str, str] = {}
    for _, row in pmid_df.iterrows():
        value = row.get("pmid")
        if pd.notna(value):
            pmid_by_study[row["srp_accession"]] = str(int(value)) if isinstance(value, float) else str(value)

    return {
        accession: StudyCrossref(
            study_accession=accession,
            geo_accession=geo_by_study.get(accession, ""),
            pmid=pmid_by_study.get(accession, ""),
        )
        for accession in study_accessions
    }


def apply_crossrefs_to_studies(studies: list[StudyRow], crossrefs: dict[str, StudyCrossref]) -> list[StudyRow]:
    updated: list[StudyRow] = []
    for study in studies:
        ref = crossrefs.get(study.study_accession)
        if ref is None:
            updated.append(study)
            continue
        notes = study.notes
        if ref.pmid:
            notes = f"{notes}; PMID:{ref.pmid} (DOI/title not resolved -- needs a further lookup)"
        updated.append(replace(study, geo_accession=ref.geo_accession, notes=notes))
    return updated
