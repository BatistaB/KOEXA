# ADR 0002: AFED reference-implementation audit

Date: 2026-09-20
Status: Accepted (informational; revisit before Milestone 7)

## Sources

- Article: Brian M. Mack and Matthew D. Lebar, "AFED, a comprehensive
  resource for *Aspergillus flavus* gene expression profiling," *Database*,
  2025, baaf033. https://doi.org/10.1093/database/baaf033
- Code: https://github.com/kcamnairb/a_flavus_expression_db
- Live app: https://a-flavus-expression-db-jyqnpeuvta-uc.a.run.app/
- License file (`LICENSE`, MIT):
  "Copyright (c) 2023 Brian Mack"

This audit was performed via web search/fetch (no local clone), per spec
section 40 item 2 ("audit the AFED article, MIT-licensed repository, data
model, interface, and reusable components") ahead of any code reuse.
A closer read of the actual source files (not just the README/license) is
recommended before any AFED code is copied or adapted verbatim, since this
audit relied on fetched summaries rather than a full repository clone.

## License

MIT License, copyright (c) 2023 Brian Mack. AOED may reuse/adapt AFED code
as long as the MIT license text and this copyright notice are preserved in
any file substantially derived from it, and the article above is cited in
AOED documentation/publications (already done in `README.md`). This audit
did not find any additional license constraints (e.g. no dual-licensing,
no CC-BY-NC data restriction mentioned in the fetched material).

## Tech stack

- **R + Shiny** for the interactive web application (`shiny_app/`).
- **R Markdown** for data-processing scripts (`src/`).
- Pipeline dependencies: `rentrez` (R, NCBI querying), `fastp` (read
  QC/trimming), `STAR` (alignment + counting), then TPM calculation.
- Dependency pinning via `shiny_renv.lock` (R `renv`).
- No dedicated database engine (SQLite/DuckDB/Postgres) was found; expression
  data is kept as R objects (e.g. RDS-style matrices) consumed directly by
  the Shiny app.

## Directory structure (as audited)

```text
a_flavus_expression_db/
├── LICENSE
├── README.md
├── shiny_renv.lock
├── src/            # discovery + processing pipeline (NCBI query, fastp, STAR, TPM)
└── shiny_app/       # Shiny application code
```

## Interface / UX patterns worth reusing

The Shiny app is reported to expose five interactive views, matching the
functional targets already listed in PROJECT_MASTER_SPEC.md sections 2.1,
24, and 33 ("Interface"): gene search and per-sample expression barplots,
sample metadata browsing, heatmaps, PCA, co-expression networks, and
genome-browser (JBrowse-style) visualization. AOED's Milestone 7 scope
(AO09/UniProt/name/alias search, per-gene barplots, BioProject/condition
filters, sample metadata/QC, heatmap, PCA, downloadable tables) is designed
to reach functional parity with this subset before adding co-expression and
genome-browser support in Milestone 8, per spec section 24/33.

## What AOED reuses vs. replaces

| AFED component | AOED decision | Rationale |
|---|---|---|
| MIT license/citation | Reuse (attribution required) | Legal requirement, already reflected in README/AGENTS. |
| Interface layout (search, barplot, heatmap, PCA, downloads) | Reuse as UX benchmark | Spec section 24/33 explicitly targets this as the first-layer product benchmark. |
| STAR-based alignment + counting | **Not** reused as the primary route | Spec section 9 prefers Salmon transcript quantification to avoid permanently retaining BAM files on a "modest PC"; STAR is kept only as an optional secondary route for genome-aligned coverage/JBrowse. |
| `rentrez`/manual NCBI querying | **Not** reused directly | Spec section 0/23 prefers `pysradb` + official NCBI/ENA APIs plus `nf-core/fetchngs` for reproducible, checksum-validated acquisition rather than a bespoke R script. |
| Ad hoc R-object storage (no DB) | **Not** reused | Spec section 8 requires DuckDB-backed, queryable, provenance-tracked storage; AOED's scientific/business state also has to interoperate with Nextflow's own execution state (section 6), which a flat R-object store does not support. |
| R + Shiny app layer | Tentatively reused for Milestone 7 | Spec section 33 explicitly says to "begin from the MIT-licensed AFED Shiny implementation or reproduce its behavior with a justified alternative." Given the rest of AOED is Python/DuckDB-based, the Milestone 7 implementer should confirm whether an R/Shiny app reading from DuckDB (via `duckdb`'s R client) or a Python-native app (e.g. Shiny for Python, Streamlit, Dash) better serves "extensibility" and "performance" (spec priorities 8-9) before committing. This ADR does not decide that; it is deferred to Milestone 7 and should get its own ADR then. |

## Follow-up: AFED's discovery query strategy (2026-09-20, for Milestone 2)

Before implementing `atlas discovery report`, read the actual source of
`src/get_sra_metadata.Rmd` in the AFED repository (not just the README, per
this ADR's original recommendation). It identifies *A. flavus* RNA-Seq
experiments with a single `rentrez::entrez_search` call:

```r
entrez_search(db='sra',
  term='(Aspergillus flavus[Organism] & transcriptomic[Source]) | ("A. flavus" & transcriptomic[Source]) | ("Aspergillus flavus" & transcriptomic[Source])',
  retmax=10000)
```

i.e. organism + library-source=transcriptomic, with a couple of literal
name-string variants. This ADR's original decision (rentrez not reused;
`pysradb` + official APIs instead) stands, but the underlying *search
intent* is directly reusable: `atlas discovery report` queries pysradb's
SRA search with the equivalent structured filters
(`--organism "Aspergillus oryzae" --strategy "RNA-Seq"`) rather than
inventing a different discovery heuristic from scratch. It found 458 A.
oryzae RNA-Seq runs across 58 BioProjects (2026-09-20) — a similar order of
magnitude to AFED's ~900 runs for the sibling species. AFED's script also
post-filters out mislabeled-organism rows (e.g. a stray "fumigatus" strain
value) after the search; `atlas discovery report` does an equivalent check
(`sample_scientific_name` must mention "oryzae"), which caught one run with
a blank organism field in NCBI's own metadata.

## Open questions for Milestone 7 (not resolved by this audit)

1. Shiny (R) vs. a Python-native dashboard framework, given AOED's backend
   is otherwise Python + DuckDB.
2. Whether AFED's genome-browser integration is JBrowse-based specifically,
   and whether that same approach is practical once AOED has STAR-derived
   coverage (spec section 9, "AFED-equivalent extensions", Milestone 8).
3. A full side-by-side of AFED's TPM/normalization method against AOED's
   Salmon-based pipeline (spec section 9) to document any expected
   numerical differences in the eventual data/QC/limitations report
   (Milestone 8).
