# 0007 — Study annotations (paper + summary) and a shared sample-tag vocabulary

Status: accepted (2026-10-03).

## Context

Clicking a study showed only repository metadata. To interpret samples (and, later, to let an LLM look for
relations across hundreds of studies) each study needs its originating paper, a very short description of
what was compared and found, and per-sample attributes that are comparable *between* studies. The curated
`conditions.tsv` columns are free text and study-shaped ("arm 'ctrl' (mapping unresolved)"), which is
right for provenance but not for cross-study querying.

## Decision

1. **One curated JSON per study** — `metadata/study_annotations/<BIOPROJECT>.json` — is the source of
   truth for paper, `study_summary` (objective / experimental_design / main_finding) and tags. DuckDB
   tables `study_annotations`, `sample_tags`, `tag_vocabulary` (migration 0002) and the web export
   `study_annotations.json` are derived (truncate-and-reload, like conditions).
2. **Paper association only at accession level**: NCBI elink BioProject→PubMed, or the paper's own
   deposition statement naming the BioProject/SRA/GEO accession. Papers that merely re-use the data are
   recorded in notes, not associated. `paper.status` is `found` / `not_found` / `ambiguous`; nothing is
   inferred from topic similarity.
3. **Tags are independent attributes**, many per sample, assigned per curated condition through reusable
   tag sets (+ optional per-run extras). The vocabulary (`metadata/sample_tag_vocabulary.tsv`) is open —
   curators add rows — but every row has a category, a definition and the synonyms it absorbs; a synonym is
   rejected with the canonical tag named, which is what keeps near-duplicates (`solid_state_culture`,
   `solid_fermentation`) out. Values that are inherently numeric/named are parametric families validated by
   regex (`30C`, `72h`, `3h_post_treatment`, `ph_5_5`, `strain_rib40`, `del_faaA`, `oe_cutL1`).
4. **Provenance per tag** (`source`, `confidence`, optional `note`) is stored in the DB; the UI shows only
   tag names.
5. **Pipeline split: collection is automatic, judgement is curated.** `atlas annotate collect --missing`
   runs inside `atlas refresh` (network failure = skipped step, never fatal) and writes
   `reports/study_evidence/<BIOPROJECT>.json`; writing the annotation is done by a curator/agent following
   `.claude/skills/annotate-study/SKILL.md`, and `refresh` lists studies still lacking one. A fully
   unattended LLM step (Claude API) can be added later on top of the same evidence files and validator;
   it was not added now so no unreviewed text reaches the database.

## Conventions worth knowing

- Time: `<N>h` = culture age (days × 24); `<N>h_post_treatment` = time since treatment/shift onset, used
  for time-matched controls too. They are deliberately different tags.
- `surface_culture` (agar/cellophane, some papers call it "solid culture") is distinct from `solid_state`
  (koji-type solid-substrate fermentation).
- `control` = the reference group of the study's main comparison (untreated, or the reference genotype);
  `baseline` = pre-treatment sample of a culture that is later treated.
- Every mycelium sample is tagged `mycelium`, so absence of the tag means a different material (conidia).

## Consequences

- First pass (2026-10-03): 8/8 studies have an originating paper (all open access, all confirmed by a
  deposition statement or elink); 52 vocabulary tags; 3,064 sample-tag rows.
- The PRJDB37930 and PRJNA121091 papers resolve fields that `conditions.tsv` marks unresolved (hypoxia arm
  mapping, AOXA = ΔaoxA, ER-stress inducer = 20 mM DTT). Recorded in the annotation notes; the
  conditions file itself was not edited.
