"""Study groups: several BioProjects that are really one study.

Some depositors register one BioProject per sample (e.g. the JGI
"Substrate Gene Expression Profiling" series: one BioProject, BioSample and
run each, replicates and time points spread over 26 BioProjects). The atlas
treats the BioProject as the study everywhere downstream (leave-one-study-out
validation, within-study co-expression, annotations, the study chart), so
26 single-sample "studies" would distort all of those.

`metadata/study_groups.tsv` (columns: bioproject, study_id) maps each member
BioProject to a study id. `atlas database load-discovery` applies it while
loading: `samples.bioproject` and the dataset row carry the study id, and
`samples.source_bioproject` keeps the original accession so provenance is
never lost. Everything downstream keeps reading `samples.bioproject`
unchanged. Without the file (or with an empty one) nothing is grouped.
"""
from __future__ import annotations

import re
from pathlib import Path

import pandas as pd

__all__ = ["load_study_groups", "group_description"]

_STUDY_ID = re.compile(r"^[A-Za-z][A-Za-z0-9_\-]*$")


def load_study_groups(path: Path) -> dict[str, str]:
    """{member bioproject: study_id}. Empty if the file does not exist."""
    if not path.is_file():
        return {}
    frame = pd.read_csv(path, sep="\t", dtype=str, keep_default_na=False)
    missing = {"bioproject", "study_id"} - set(frame.columns)
    if missing:
        raise ValueError(f"{path.name}: missing column(s) {sorted(missing)}")
    frame = frame[(frame["bioproject"] != "") & (frame["study_id"] != "")]
    duplicated = frame[frame["bioproject"].duplicated()]["bioproject"].tolist()
    if duplicated:
        raise ValueError(f"{path.name}: bioproject listed more than once: {duplicated}")
    for study_id in frame["study_id"].unique():
        if not _STUDY_ID.match(study_id):
            raise ValueError(f"{path.name}: study_id '{study_id}' must start with a letter and use only letters, digits, '_' and '-'")
    clash = set(frame["study_id"]) & set(frame["bioproject"])
    if clash:
        raise ValueError(f"{path.name}: study_id equals a member bioproject: {sorted(clash)}")
    return dict(zip(frame["bioproject"], frame["study_id"]))


def group_description(descriptions: list[str], n_members: int) -> str:
    """Common wording of the members' descriptions, minus the part that differs
    (e.g. the trailing sample code), plus a note on how many BioProjects it groups."""
    prefix = descriptions[0] if len(descriptions) == 1 else _common_prefix(descriptions)
    prefix = re.sub(r"[\s\-–:.,;\d]+$", "", prefix)
    return f"{prefix} ({n_members} BioProjects grouped as one study)" if prefix else f"{n_members} BioProjects grouped as one study"


def _common_prefix(values: list[str]) -> str:
    first, last = min(values), max(values)
    n = 0
    while n < len(first) and n < len(last) and first[n] == last[n]:
        n += 1
    return first[:n]
