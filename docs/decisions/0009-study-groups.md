# 0009 - Study groups: several BioProjects counted as one study

Status: accepted (2026-10-22)

## Context

The atlas uses the BioProject as the *study* everywhere downstream:
leave-one-study-out validation and `n_studies` (`rank`), within-study
co-expression (`coexpr`), the unit id of the expression matrix, one annotation
file per study, and the study-stacked home chart.

Some depositors register one BioProject per sample. The JGI series
"*Aspergillus oryzae* RIB40 Substrate Gene Expression Profiling - 4.X.Y.Z"
(26 BioProjects in the atlas, 1 BioSample and 1 run each) is one experiment:
5 substrates (D-xylose, D-xylan, D-xyloglucan, WB, SBH) x 2 times (2 h, 8 h)
x 3 replicates. Left as 26 studies it would raise the study count from 22
to 48, make every "leave one study out" a single-sample test, drop the block
from within-study co-expression, put 26 one-sample bars in the home chart and
prevent the replicates from being recognised as replicates.

## Decision

`metadata/study_groups.tsv` (`bioproject`, `study_id`) maps member BioProjects
to a study id. `atlas database load-discovery` applies it while loading:

- `samples.bioproject` (the study key all downstream code reads) holds the
  study id, so matrix, rank, co-expression, annotation and export need no change;
- `samples.source_bioproject` (migration 0003) keeps the accession the run
  was deposited under - provenance is never lost; it equals `bioproject` for
  every ungrouped sample;
- the member rows of `datasets` are replaced by one row (`dataset_id` =
  `bioproject` = study id) whose notes list the members;
- `annotate collect` skips study groups (it queries NCBI per BioProject); the
  group's annotation is written by hand from the members' records, and its
  file is `metadata/study_annotations/<study_id>.json`.

Condition ids of a group follow the usual rule with the study id in place of
the BioProject (`JGI-RIB40-substrates_xylan_8h`). Without the file, or with
an empty one, nothing is grouped.

## Consequences

- `samples.bioproject` can now hold a non-accession study id; code that needs a
  real accession (links to NCBI, provenance) must use `source_bioproject`.
- Grouping is a curatorial judgement (same depositor, same design, same
  protocol); it is recorded in the TSV, not inferred.
- A group's `study_id` must not equal any member accession and must match
  `[A-Za-z][A-Za-z0-9_-]*` (checked on load).

First use: `JGI-RIB40-substrates` (26 BioProjects).
