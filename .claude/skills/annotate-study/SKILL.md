---
name: annotate-study
description: Enrich a KOEXA study (BioProject) with its originating paper, a 3-part summary (objective / experimental design / main finding) and per-sample tags from the shared vocabulary. Use when a new study enters metadata/samples.tsv, when `atlas refresh` / `atlas annotate status` reports a study that "needs curation", or when the user asks to annotate, tag, or find the paper for a study.
---

# Annotate a study

Goal: turn each study into `Study -> objective -> design -> main finding -> samples -> tags`, short and
consistent enough that an LLM can later compare hundreds of studies. Not a paper review.

Output: `metadata/study_annotations/<BIOPROJECT>.json` (the source of truth; DB tables and
`app/web/public/data/study_annotations.json` are derived from it). Copy the structure of an existing
file, e.g. `metadata/study_annotations/PRJDB4747.json`.

## 1. Collect evidence (automatic)

```
.\run_atlas.ps1 annotate collect <BIOPROJECT>        # or: annotate collect --missing
```

Writes `reports/study_evidence/<BIOPROJECT>.json`: accession-linked paper candidates (NCBI elink +
Europe PMC full-text accession search) with abstract, DOI/PMID/PMCID, and the full-text sentences that
mention the accession; plus the study's SRA sample titles, atlas samples and curated conditions.

## 2. Decide the paper association — never guess

- `found` only when the paper is linked at accession level: NCBI elink, or its text says the data were
  **deposited** under this BioProject/SRA/GEO accession (`deposition_statement: true`).
- A paper that only *cites/re-uses* the accession is not the originating paper (record it in `notes`).
- Several plausible originating papers, or only topical matches → `ambiguous`; nothing → `not_found`.
  Keep `study_summary` anyway, written from the BioProject/SRA description.
- Open-access full text (`https://www.ebi.ac.uk/europepmc/webservices/rest/<PMCID>/fullTextXML`): read
  Methods for the design. Otherwise use abstract + metadata, set `paper.access` accordingly.
- If the design genuinely cannot be understood without the PDF, set `curation.needs_pdf: true`, write
  what you can, and tell the user exactly which study needs the PDF.

## 3. Write the summary (2-4 sentences total)

- `objective`: what the authors wanted to learn (1 sentence).
- `experimental_design`: what was compared — strains, conditions, times, replicates (1 sentence).
- `main_finding`: the result most useful for interpreting these transcriptomes (1 sentence).
Each field <= ~2 short sentences (validator rejects > 600 chars). English, plain, no hype.

## 4. Tag every sample

Tags are assigned per curated `condition_id` (all replicate runs share them) through reusable
`tag_sets`; `sample_tags` adds per-run extras. Every run of the study must end with >= 1 tag.

Rules:
- **Reuse first.** Tags come from `metadata/sample_tag_vocabulary.tsv` or a parametric family:
  `30C`, `24h` (culture age, days x 24), `3h_post_treatment` (time since treatment; also for
  time-matched controls), `ph_5_5`, `strain_rib40`, `del_<gene>`, `oe_<gene>`.
  Before adding a vocabulary row, run `.\run_atlas.ps1 annotate suggest "<concept>"`. Synonyms are
  rejected with the canonical tag named (e.g. `liquid_culture` -> `submerged`).
- **Never study-specific** (`glucose`, not `glucose_PRJDB4747`); never force a wrong existing tag either —
  add a new row (tag, category, one-line definition, synonyms) when the concept is genuinely new.
- Cover what applies: role (`control`/`treated`/`baseline`), genotype + strain, biological material,
  growth phase, culture system, medium, carbon/nitrogen source, substrate, compounds, stress, oxygen,
  temperature, pH, time, industrial context. Skip categories the study doesn't specify.
- Tag consistently across studies: e.g. every mycelium sample gets `mycelium`; liquid cultures get
  `submerged`; agar/cellophane is `surface_culture`, not `solid_state` (koji-type SSF only).
- Each tag: `{"tag", "source", "confidence", "note"?}`. `source` is one of `sample_metadata`,
  `bioproject_description`, `curated_condition`, `paper_methods`, `paper_abstract`,
  `inferred_from_methods`, `inferred_from_design`. Prefer stated facts; mark inferences as such with
  `medium`/`low` confidence and a short note.
- If the paper resolves something `metadata/conditions.tsv` left unresolved, say so in `notes` and
  offer the user a conditions.tsv correction (do not silently edit curated conditions).

## 5. Validate, load, export

```
.\run_atlas.ps1 annotate validate
.\run_atlas.ps1 database load-annotations
.\run_atlas.ps1 app export-web          # or simply: .\run_atlas.ps1 refresh
```

Fill `curation.curated_by` / `curated_at`. Report to the user: paper found (with DOI) or not, and
any new vocabulary tags you created.
