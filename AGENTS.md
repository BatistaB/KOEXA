# Instructions for coding agents (Codex, Claude, or otherwise)

This file governs any AI agent working in this repository. It summarizes and
does not replace `PROJECT_MASTER_SPEC.md` (section 0 and section 38); read
that file in full before making changes, and treat any conflict between this
file and the spec as a bug in this file.

## Non-negotiable priorities, in order

1. Data integrity
2. Reproducibility
3. Safe storage management
4. Traceability/provenance
5. Resumability after interruption
6. Quality control
7. Correct biological metadata
8. Extensibility
9. Performance

## Hard rules

- Never fabricate accession numbers, reference versions, or biological
  metadata. Unknown values are stored as explicitly unknown, never guessed.
- Never start large downloads or large-scale processing without explicit
  human approval. Discovery and download are separate phases.
- Never delete raw/intermediate files until the corresponding compact output
  has been validated and registered (see spec section 5, Storage Guardian).
  A quantification command exiting 0 is not sufficient justification.
- Never average biological replicates during ingestion. They remain
  independent columns/rows; aggregation is a derived, separate table.
- Never let downstream classification (clustering, biological labels)
  overwrite or replace the raw processed measurements.
- Keep the canonical AO09 gene identifier system as the primary key.
  UniProt/alias identifiers are secondary and map through an explicit,
  auditable table; ambiguous mappings stay ambiguous.
- Log every important operation (spec section 26). A future reader must be
  able to answer "exactly how was this value generated?".
- Work milestone-by-milestone (spec sections 37-38). Do not implement
  visualization, entropy, or clustering features ahead of the acquisition,
  QC, and database layers they depend on.
- Reuse `nf-core/fetchngs`, `nf-core/rnaseq`, and Nextflow rather than
  reimplementing download/QC/quantification. AOED-specific code is limited to
  identifier reconciliation, condition curation, database ingestion, storage
  policy, atlas construction, and downstream analyses.
- Any code substantially derived from AFED (MIT license) must retain its
  license/copyright notice and be cited.
- Prefer small, reproducible dry-runs. Report disk/storage estimates before
  scaling up.
- Ask the user when a biological or irreversible decision cannot be made
  safely from the information available.

## Working agreement

- Maintain `TODO.md` as work progresses.
- Record non-trivial design decisions under `docs/decisions/`.
- Run tests after meaningful changes (`pytest`, once dependencies are
  installed in the target Python environment).
- Keep scientific calculations in tested functions in `src/`, not only in
  notebooks. Notebooks are for exploration/reporting.
