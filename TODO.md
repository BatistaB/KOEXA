# TODO — AOED / Aspergillus oryzae Transcriptome Atlas

Tracks live progress against the milestones in `PROJECT_MASTER_SPEC.md`
section 37. Keep this file honest: check an item only when it is actually
done, not scaffolded.

## Milestone 0 — Repository and runnable AOED shell (COMPLETE)

- [x] Create project directory structure (config/, metadata/, workflows/,
      reference/, scratch/, runtime/, results/, database/, matrices/,
      analysis/, reports/, app/, src/aoryzae_atlas/, notebooks/, tests/,
      docs/decisions/).
- [x] `config/reference.yaml`, `pipeline.yaml`, `qc.yaml`, `storage.yaml`
      (no invented accessions; reference left unfrozen).
- [x] `metadata/*.tsv` schema-only files.
- [x] CLI skeleton (`atlas init`, `atlas doctor`, `atlas status`,
      `atlas storage status`) plus stubs for every other section-25 command.
- [x] `run_atlas.ps1` Windows launcher (venv bootstrap + CLI forwarding).
- [x] `pyproject.toml`, `.gitignore`, `README.md`, `AGENTS.md`.
- [x] Initial pytest tests for config loading and CLI commands.
- [x] AFED audit (license, stack, structure) — see `docs/decisions/`.
- [x] Decide and record the container/execution strategy for Nextflow/nf-core
      on the user's machine: Docker Desktop (already installed) as the
      container engine, Nextflow running inside a WSL2 Ubuntu distro. See
      `docs/decisions/0003-execution-strategy.md`.
- [x] Confirmed Docker Desktop uses the WSL2 backend (default engine;
      `settings-store.json` has no `useWindowsContainers` override, and
      `docker version` reports a Linux-engine server). Installed a
      general-purpose Ubuntu WSL2 distro (`wsl --install -d Ubuntu`),
      created a non-root default user (`bruno`, `sudo` group, default set
      via `/etc/wsl.conf`), and installed OpenJDK 17 and Nextflow 26.04.6
      (`/usr/local/bin/nextflow`) inside it.
- [x] Docker Desktop WSL integration enabled for the "Ubuntu" distro by the
      user (Settings > Resources > WSL integration > Apply & Restart).
      Verified with `wsl -d Ubuntu -- docker version` (Linux engine reachable)
      and `docker run --rm hello-world` (image pulled and ran successfully).
- [x] Set up a real Python environment on the user's Windows machine and
      confirmed `run_atlas.ps1 doctor` passes there. This also uncovered and
      fixed two real bugs in `run_atlas.ps1`: (1) `Resolve-BasePython`
      trusted `Get-Command` alone, so a broken/non-functional `py` launcher
      stub on this machine (`C:\WINDOWS\system32\py`, a Python Manager
      artifact, not a real console app) was silently accepted and the venv
      creation step failed with no visible error; (2) PowerShell's `..`
      range operator counts down when start > end (`1..0` yields `@(1,0)`,
      not empty), which corrupted the argument list for single-word
      interpreter commands like `python3`/`python`. Both are fixed with an
      actual-execution check and a safe `Get-ExtraArgs` helper. Full pytest
      suite (22 tests) passes.

## Milestone 1 — AO09 and UniProt reconciliation

- [x] User supplied a full FungiDB release 71 evidence set for
      *A. oryzae* RIB40 under `database/FungiDB_v71/` (GFF, annotated
      CDS/protein/transcript FASTAs, GO associations, gene aliases, gene
      product updates, and the UniProt-derived workbook
      `Archive_9_PSIM_Aory.xlsx`). SHA256 checksums recorded in
      `database/FungiDB_v71/CHECKSUMS.sha256`; provenance notes in
      `database/FungiDB_v71/PROVENANCE.md`. Payload files are gitignored
      (same policy as `/reference/`); only the checksums/provenance files
      are tracked.
- [x] Implemented and ran `atlas identifiers reconcile`
      (`src/aoryzae_atlas/identifiers/`, 21 new tests) comparing the
      workbook's AO09 gene references (scanned from both the UniProt
      "Genes" and "Aliases" fields, since fused/tandem-ORF entries only
      list the second locus in Aliases) against the 12,090 genes in the
      FungiDB v71 RIB40 protein FASTA. Neither file is treated as the
      canonical/frozen reference (that is Milestone 3). Results:
      12,185 UniProt-entry/AO09 links from 12,078 distinct UniProt entries;
      11,483 exact, 120 one-to-many, 10 many-to-one, 572 unmapped (AO09 ids
      the workbook references that do not exist in FungiDB v71 -- likely
      retired/renumbered ids); 18 duplicate UniProt entries in the workbook;
      562 FungiDB v71 genes with no UniProt coverage at all (notably a long
      contiguous run under the `AO090701*` contig). Full audit trail in
      `metadata/gene_id_mapping.tsv`; full report in
      `reports/gene_id_mapping_summary.txt`.
- [ ] Open provenance question (see `database/FungiDB_v71/PROVENANCE.md`):
      which exact UniProt query/reference-proteome/date the workbook was
      built from. Not required to produce `gene_id_mapping.tsv` (its
      `reference_version` column correctly records `FungiDB_v71`, the AO09
      evidence snapshot, not a UniProt release), but needed before
      `gene_external_identifiers.tsv` rows can cite a real UniProt
      source_version.
- [x] Populated `metadata/gene_external_identifiers.tsv` (35,662 rows):
      UniProtKB_accession/UniProtKB_entry_name (11,533 each, one pair per
      non-unmapped `gene_id_mapping.tsv` row) and gene_alias (690 rows, from
      non-AO09 tokens in the workbook's Aliases field) from the UniProt
      workbook; FungiDB (11,906 rows, the "AO07"-prefixed alternate gene id)
      from `GeneAliases.txt`. Rows whose AO09 id is "unmapped" (not present
      in FungiDB v71) are excluded -- that raw claim stays in
      `gene_id_mapping.tsv` only.
      While building this, discovered `GeneAliases.txt` is **not** the fixed
      3-column format a small initial sample suggested: the real file has
      2-9 tab-separated columns per row (verified across all ~12k rows),
      mixing tRNA-gene rows (non-AO09 primary id), "AO07"/"AO08"-prefixed
      ids, "AOR_..." ids, occasional extra AO09 ids (apparently
      merged/retired loci -- worth revisiting when investigating the 562
      "missing" genes below), and a trailing AspGD "ASPL..." id. Only the
      well-understood "AO07..." token is mapped to a namespace for now;
      `fungidb.load_gene_aliases()` was generalized to variable-length rows
      and the others are deliberately left unmapped rather than guessed
      (raw alias list kept in each row's `evidence` field either way).
      Also fixed a real bug found while spot-checking: `explode_uniprot_gene_links`
      was over-counting links for UniProt entries that the workbook's own
      upstream processing had pre-exploded into multiple rows (repeating the
      same Aliases text on each row) -- corrected counts are in the
      Milestone 1 entry above. 4 new tests added for the variable-column
      parser and the namespace-filtering logic (45 total, all passing).
- [x] Populated `metadata/gene_master.tsv` (12,090 rows, one per FungiDB v71
      protein-coding gene): coordinates/strand from the GFF3
      (`src/aoryzae_atlas/metadata/gff.py`, scoped to the `protein_coding_gene`
      feature type only -- the file also carries mRNA/exon/CDS/UTR features
      and non-coding genes/tRNA/rRNA below or outside that level), and
      `description` from `gene_product_updates_b71.txt`'s `b71_product`
      where available (563 genes), else the GFF's own `description`
      attribute (URL-decoded). `gene_symbol`/`gene_name` are deliberately
      left blank: the only symbol evidence is the UniProt workbook's
      "Aliases" field, which lists multiple tokens per gene with no
      reliable way to pick a primary one (that full set is already in
      `gene_external_identifiers.tsv` as `gene_alias` rows, without picking
      a winner) -- promoting one to `gene_master.tsv` here would be a guess.
      New `atlas genes build-master` CLI command; 6 new tests (51 total,
      all passing).
- [x] Investigated the 562 "no UniProt coverage" genes and 572 "unmapped"
      workbook ids using a lead noticed earlier: some `GeneAliases.txt` rows
      list an *extra* AO09-pattern token among a current gene's aliases
      (e.g. primary `AO090011000964` lists alias `AO090011000551`) --
      evidence of a retired/renumbered id from an older annotation version.
      Built `fungidb.build_ao09_redirect_map()` (only trusts a redirect
      whose target is itself a confirmed current gene; verified
      exhaustively that no old id maps to more than one current gene in
      this release) and `reconcile.apply_ao09_redirects()`, wired into
      `atlas identifiers reconcile` via the existing `--gene-aliases`
      option. Result: **all 566** unmapped workbook ids resolve through
      this redirect to a current gene (mapping_type `annotation_alias`,
      confidence `medium`, the spec's own vocabulary for exactly this
      case), and **274 of the 562** "no coverage" genes turn out to have
      indirect UniProt evidence this way -- cutting genuinely
      UniProt-uncovered genes from 562 to **288**, almost all still
      concentrated in the `AO090701*` contig (worth a closer look, e.g.
      whether that contig was added/renumbered wholesale in a later
      release). `gene_id_mapping.tsv` (12,099 rows: 11,483 exact, 39
      one-to-many, 11 many-to-one, 566 annotation_alias, 0 unmapped) and
      `gene_external_identifiers.tsv` (36,810 rows) regenerated. 4 new
      tests (70 total, all passing).
- [ ] Not yet decided: whether `database/FungiDB_v71/` should move under
      `reference/` to match PROJECT_MASTER_SPEC.md section 7's layout
      (`database/` is specified to hold only `atlas.duckdb`). Left as-is
      for now; easy to `git mv` later since payloads are gitignored either
      way.

## Milestone 2 — Public transcriptome discovery report

- [x] Implemented `atlas discovery report` (`src/aoryzae_atlas/discovery/`):
      queries NCBI SRA via `pysradb` (organism="Aspergillus oryzae",
      strategy="RNA-Seq") — reproducing AFED's own discovery-search intent
      (`get_sra_metadata.Rmd`'s `entrez_search(term='(Aspergillus
      flavus[Organism] & transcriptomic[Source]) | ...')`) through the
      pysradb/official-API route `docs/decisions/0002-afed-audit.md`
      already decided on instead of AFED's rentrez script. Metadata only —
      no FASTQ/SRA data downloaded, nothing approved for processing.
      Real run (2026-09-20): 458 runs, 439 BioSamples, 58 BioProjects, 1
      run excluded (blank organism field in NCBI's own metadata). Writes
      `reports/discovery/{studies,samples,runs,exclusions}.tsv`,
      `discovery_<date>.md`, and the raw pysradb response under
      `raw_api_responses/` for provenance. 11 new tests (62 total, all
      passing), all using synthetic fixtures (no test depends on live
      network access).
- [x] Implemented the deferred GEO/PMID enrichment pass:
      `discovery/crossref.py` + `atlas discovery report --enrich-crossrefs`,
      batching all study accessions into one `pysradb` `srp-to-gse`/
      `srp-to-pmid` call each (much cheaper than one call per study). Real
      run (2026-09-20): 3/58 studies have a GEO accession, 3/58 have a
      PMID (one study has both). `publication_doi`/`publication_title`
      still left blank even when a PMID is found -- that needs a further
      PMID -> article-metadata hop, not yet implemented. 3 new tests (65
      total at that point).
- [ ] Known gaps, deliberately deferred rather than guessed:
      - No AO09/RIB40 reference-compatibility-risk assessment per study yet
        (spec section 23) — needs a human to read the condition_clues/
        strain text.
      - No `RECOMMENDED_MVP` selection: every study/sample/run that passed
        basic organism/strategy/source checks is `REQUIRES_REVIEW`, not
        auto-approved. Spec section 23 asks for a manually curated, diverse
        representative set (submerged/solid-state, carbon sources, stress,
        growth phase, strain) — picking that set is the next actual
        decision point, and it needs the user's input.
      - `atlas discovery export` is still a stub; unclear yet whether it
        needs to do anything beyond what `report` already writes.

## Milestone 3 — Canonical RIB40 reference (COMPLETE)

- [x] User supplied the RIB40 genome FASTA
      (`database/FungiDB_v71/FungiDB-71_AoryzaeRIB40_Genome.fasta`, 12
      sequences: 8 chromosomes, 3 unplaced contigs, 1 mitochondrial genome,
      37,912,014 bp total) alongside the annotation/transcript/protein
      FASTAs already used in Milestone 1.
- [x] Verified the assembly accession via NCBI's Assembly database
      (`esearch`/`esummary` + `datasets` API, term="Aspergillus oryzae
      RIB40"[organism], 2026-09-20): our file's total length equals
      **GCF_000184455.2** (ASM18445v3, RefSeq category "reference genome",
      NITE Japan)'s nuclear total (37,882,812 bp) plus its 29,202 bp
      mitochondrial genome, exactly. 3 other RIB40 assemblies were checked
      and ruled out (contig-level/different total length/older versions).
      Full detail in `database/FungiDB_v71/PROVENANCE.md`.
- [x] Implemented `atlas reference validate`
      (`src/aoryzae_atlas/reference/`): cross-checks genome/GFF/protein/
      transcript files against each other, computes checksums, and builds
      `reference/transcripts/t2g.tsv` (transcript-to-gene mapping for
      Salmon-output gene-level aggregation later). Real run: 0 problems --
      GFF and protein FASTA gene sets match exactly at 12,090 genes, t2g
      genes are a full subset of the GFF. Does **not** build a Salmon index
      (deferred to Milestone 5 via nf-core/rnaseq's own pinned
      reference-building subworkflow, per AGENTS.md's "reuse nf-core"
      rule) and does **not** flip `frozen: true` on its own. 8 new tests
      (76 total, all passing).
- [x] Populated `config/reference.yaml` with the verified
      `assembly_accession`, `reference_version: "RIB40_v1"`, file paths,
      and checksums. `annotation_accession` stays null on purpose: the
      FungiDB v71 annotation (GFF source=VEuPathDB) is FungiDB's own
      curation, not verbatim NCBI RefSeq gene models, and has no separate
      NCBI-style accession of its own. **`frozen` is still `false`** --
      that flip needs the user's explicit sign-off (spec section 37:
      "stop and report if AO09/reference assumptions remain unclear"),
      not something this pass decides on its own.
- [ ] Open layout question (same one noted under Milestone 1): the
      reference files live in `database/FungiDB_v71/`, not
      `reference/{genome,annotation,transcripts}/` per spec section 7's
      layout. `reference.yaml`'s paths point at the actual current
      location rather than duplicating ~100MB of payload; revisit if a
      move is wanted later.
- [x] User sign-off received 2026-09-20; `config/reference.yaml` is now
      **frozen** (`frozen_at: 2026-09-20T17:00:00Z`,
      `frozen_by: Bruno Batista <bruno.batista.biotec@gmail.com>`).
      **Milestone 3 is complete.**

## Milestone 4 — Database, state, and storage safety

- [x] Created the DuckDB schema (`src/aoryzae_atlas/database/migrations/
      0001_initial_schema.sql`) for all 7 core tables from spec section 8
      (datasets, samples, conditions, genes, gene_external_identifiers,
      sample_qc, processing_events, gene_expression), plus a minimal
      forward-only migration runner (`database/migrate.py`,
      `atlas database migrate`) tracked in a `_schema_migrations` table.
      `samples.sample_id` = run accession (SRR/DRR/ERR...), the finest
      granularity nf-core/rnaseq actually processes.
- [x] Implemented `atlas database load-genes` (loads `gene_master.tsv` +
      `gene_external_identifiers.tsv`; both fully derived and deterministic,
      so each run truncates and reloads) and `atlas database load-discovery`
      (loads `reports/discovery/{studies,samples,runs}.tsv` into
      `datasets`/`samples` -- the "STORE METADATA" step of spec section
      23's discover -> store -> review -> approve -> queue -> process
      workflow). `samples` rows are **upserted**, not replaced:
      `pipeline_status`/`qc_status`/`quant_status`/`exclusion_reason` are
      only set the first time a run is seen, so a later re-discovery pass
      can never reset a sample that has since been approved/queued/
      processed back to its initial discovery status -- verified with a
      dedicated test that simulates this exact scenario.
      Real run: 12,090 genes, 36,810 gene_external_identifiers rows,
      58 datasets, 458 samples loaded (457 `METADATA_REVIEW`, 1
      `EXCLUDED`, matching Milestone 2's discovery results exactly).
      `atlas status` now reports real counts from the database instead of
      hardcoded zeros (`database/queries.py`).
      13 new tests (87 total, all passing).
- [x] Implemented `atlas sample approve <SRR>` (`database/approve.py`): the
      human sign-off gate between discovery and download/processing.
      Refuses to approve an `EXCLUDED` sample, is idempotent for an
      already-`APPROVED` one (no duplicate audit row), and logs a
      `processing_events` row for every real approval. 4 new tests (91
      total, all passing).
- [ ] Not yet done: Nextflow task-state tracking, disk monitoring wired
      into the database, graceful pause/restart recovery, and safe-cleanup
      tests. Deliberately deferred to build alongside Milestone 5's actual
      pipeline orchestration rather than speculatively ahead of it -- there
      is no real Nextflow run to track state for yet, and `state.py`'s
      `SampleState` enum (already built, Milestone 0) is the vocabulary
      that tracking will use once there is one.

## Sample curation (spec section 23 "aim for diversity")

Scope clarified by the user 2026-09-20: sample approval is **not**
restricted to RIB40 -- the project deliberately wants cross-strain
comparison as a first-class analysis axis (strain becomes a filterable
atlas dimension later), not a single-strain compendium. See the
`project-cross-strain-scope` memory. Curated from `reports/discovery/`
(2026-09-20 snapshot) covering the spec's diversity axes on RIB40 data
specifically for this first, simplest round (broader non-RIB40 diversity
is a deliberate next round, not excluded):

- [x] **Approved**: `DRR786485` (BioProject PRJDB37768, "RIB40_DPY_1d",
      1 run, PAIRED, ~2.36 GB) -- simplest possible single RIB40 run,
      picked specifically to validate Milestone 5 pipeline mechanics
      before scaling up.
- [ ] Proposed, not yet approved -- awaiting the user's go-ahead on which
      (if any) to approve next:
      - Submerged + solid-state + stress, with replicates, already
        published (GEO GSE18851 / PMID 20392818): `PRJNA121091` (8 runs) --
        also a natural Milestone 6 "one replicated condition" candidate.
      - Carbon source (lactate vs glucose): `PRJDB42398` (15 runs / 5
        biosamples).
      - Growth phase/time course (1-5 days, MPY medium, 3 reps/timepoint):
        `PRJDB17490` (15 runs).
      - Chemical/lignocellulosic stress with replicates (vanillin,
        levulinic acid, HMF, furfural, 24h, 3 reps each): `PRJNA1261861`
        (83 runs total -- pick 1-2 treatment arms + control for a first
        pass, not the whole study).
      - Developmental stage (conidia / germinated conidia / hyphae):
        `PRJDB4747` (3 runs, single-end, smallest files of the set).
      - No clean RIB40 "secretion/production context" (e.g. industrial
        koji/soy-sauce) candidate was found -- the koji/Daqu studies in
        this snapshot use non-RIB40 strains (LBM 30007/30008, 3.042),
        which is fine per the scope above but wasn't bundled into this
        first RIB40-only round without the user picking it explicitly.

## Milestones 5-12

- [ ] Not started (see PROJECT_MASTER_SPEC.md section 37 for full list).
