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

## Milestone 5 — One sample end-to-end (IN PROGRESS)

- [x] **Undocumented decision, backfilled 2026-09-21**: `nf-core/fetchngs` is
      always invoked here with `--download_method ftp`, not its default
      `sratools` (prefetch + fasterq-dump). A `sratools` attempt for
      DRR786485 was made at some point before this file's own visible
      history (orphaned partial output survives at
      `results/fetchngs_sratools_test/DRR786485/`, no metadata/fastq -- it
      didn't get far), and the switch to `ftp` was never written down; by
      the time this was noticed the original run's `.nextflow.log` had
      already rotated away, so the exact failure reason is lost. Going
      forward: keep using `--download_method ftp` (downloads the
      already-converted FASTQ straight from ENA's FTP mirror via `wget`,
      one fewer moving part than sratools' download-then-convert-locally
      flow) unless a specific run needs `sratools` for a reason worth
      writing down here when it comes up.
- [x] **Critical infra finding (2026-09-20), applies to every future download,
      not just this one:** running `nf-core/fetchngs` with its Nextflow
      work dir and `--outdir` under `/mnt/d/PanTranscriptome/...` (the
      Windows-mounted drive, reached from WSL2 via the 9p/DrvFs bridge)
      produced a gzip-corrupt FASTQ (CRC/length errors on `gzip -t`,
      confirmed independently of the MD5 check) on two separate attempts,
      for the same run. Initially suspected the 9p/DrvFs bridge itself, so
      moved `-work-dir`/`--outdir` to a WSL2-native path
      (`~/aoed-scratch/...`) -- but the corruption recurred there too,
      disproving that theory. **Actual root cause**: the Windows C: drive
      had filled to 0 bytes free. The WSL2 Ubuntu distro's `ext4.vhdx` (and
      Docker's build cache, and stray temp files) lived on C: by default,
      so even "WSL2-native" paths under `~/` were physically backed by a
      file on the full C: drive -- writes failed with `Bus error`,
      `Read-only file system`, and `Input/output error`, which surfaced as
      gzip corruption in the downloaded files. A parallel test confirmed it
      wasn't network/Docker/sratools: the user downloaded the same run via
      `prefetch` on Google Colab instantly, with no issue. Fix applied:
      freed some C: space (Recycle Bin + Windows Temp), then migrated the
      whole Ubuntu WSL2 distro from C: to `D:\WSL\Ubuntu` via
      `wsl --export` / `--unregister` / `--import` (verified all data —
      `~/aoed-scratch`, `.nextflow`, `.docker` — survived intact). WSL2's
      root filesystem now reports 945GB available. `config/storage.yaml`'s
      `paths.nextflow_work_dir` comment updated to reflect the real cause.
      Docker Desktop was already installed on D: so wasn't part of the
      problem. Claude Code's own app data intentionally left on C: (user's
      call -- not worth the risk of relocating a live MSIX package's VM
      bundle just for a few GB).
- [x] Also hit and fixed along the way (see `config/pipeline.yaml`
      comments): Nextflow 26.x's new strict config parser rejects the
      `check_max()` Groovy closure nearly every nf-core pipeline's
      `base.config` still uses -- pin `NXF_VER=25.10.0` for nf-core pipeline
      invocations. And: this machine's WSL2 has only ~8.7GB RAM (host has
      ~19GB, no `.wslconfig` override) while `nf-core/fetchngs`'s default
      `SRA_FASTQ_FTP` resource label requested 12GB -- cap with
      `--max_memory 6.GB --max_cpus 4` (the exact mechanism `check_max()`
      exists for; per spec section 30 "modest PC" guidance, cap requests
      rather than grow WSL2's memory ceiling and starve the host).
- [x] Downloaded `DRR786485` (BioProject PRJDB37768) via `nf-core/fetchngs`
      1.12.0 after the C:-drive fix above -- both mates gzip-valid, exact
      expected read count (20,970,212 reads x2), MD5-verified. Output at
      `~/aoed-scratch/results/fetchngs/DRR786485/` (samplesheet + FASTQ).
- [x] **Second infra finding (2026-09-20)**: `nf-core/rnaseq` 3.26.0's
      `conf/base.config` has fully dropped `check_max()` (0 uses) in favour
      of Nextflow's native `process.resourceLimits` directive -- but only
      sets that directive inside its own `test`/`test_gpu` profiles, not
      the general `docker` profile. So `--max_memory`/`--max_cpus` are
      silently inert on this pipeline version (its process labels, e.g.
      `process_low` = fixed 12.GB, have no params.max_memory gate left at
      all) even though the exact same flags still work on `nf-core/fetchngs`
      1.12.0 (which still calls `check_max()`). Symptom: `FQ_LINT`
      (`process_low`, fixed 12GB) failed immediately with "Process
      requirement exceeds available memory -- req: 12 GB; avail: 8.7 GB".
      Fix: added `config/nextflow_resource_limits.config` (sets
      `process.resourceLimits` to cpus:4/memory:6.GB/time:240.h) and pass it
      with `-c` on any modern nf-core pipeline invocation on this machine,
      alongside `-profile docker` -- don't rely on `--max_memory`/
      `--max_cpus` alone going forward, since more pipelines will migrate
      off `check_max()` the same way.
- [x] Quantified `DRR786485` via `nf-core/rnaseq` 3.26.0 with
      `--skip_alignment --pseudo_aligner salmon` (pure Salmon
      pseudo-alignment, no BAM, per spec section 9) against the frozen
      RIB40_v1 reference (`config/reference.yaml`) -- decoy-aware index
      (genome fasta as decoy + FungiDB's own curated transcript FASTA, not
      a GffRead-extracted one, to stay consistent with the AO09 gene ID
      system). Output at `~/aoed-scratch/results/rnaseq/DRR786485/`:
      transcript- and gene-level TPM/counts (`salmon.merged.*.tsv`),
      SummarizedExperiment `.rds` files, and a MultiQC report. This closes
      Milestone 5's core technical path (download -> QC -> quantification)
      for one sample end-to-end.
- [x] **Architecture pivot (2026-09-21), see `docs/decisions/0004-colab-based-acquisition.md`**:
      attempted a second batch (PRJDB4747: DRR059464/65/66) via a new
      `workflows/process_samples.sh` batch driver (resumable, per-pipeline
      Nextflow session-id tracking to fix a `-resume` cache-mismatch bug,
      Aspera-with-ftp-fallback download). All of that plumbing is now
      **removed** (`workflows/process_samples.sh`,
      `workflows/mark_sample_status.py`, `config/nextflow_resource_limits.config`
      deleted) because it solved the wrong problem: this machine's home
      internet downloads from ENA's FTP mirror at ~2MB/min regardless of
      Nextflow/Docker/WSL2 config (confirmed via a raw `wget` of the same
      URL), while the identical download from a Google Colab notebook took
      16-170s per file. Acquisition + QC + quantification now run in
      `workflows/colab_pantranscriptome.ipynb` (direct `wget`/`fastqc`/
      `fastp`/`salmon quant` calls, no Nextflow/Docker -- Colab has no
      Docker support), with only finished per-sample results (never raw
      FASTQ) synced back via Google Drive at
      `MyDrive/PanTranscriptome/results/<accession>/`. Salmon stays the
      quantifier (spec section 9), same decoy-aware RIB40_v1 index recipe.
      `atlas sample approve` is still how a sample gets greenlit; the
      approved accession is then added to the notebook's `ACCESSIONS` list
      by hand.
- [x] Implemented `atlas process ingest <SRR>` / `atlas process ingest --all`
      (`database/ingest_results.py`): reads a Colab-produced
      `results/<accession>/` folder (`gene_quant.tsv`, `fastp.json`, `DONE`
      marker) and loads it into `gene_expression`/`sample_qc`, moving
      `pipeline_status` to `QUANTIFIED` and `reference_version`/
      `pipeline_version` to the current frozen values. Re-running for the
      same sample replaces its `gene_expression`/`sample_qc` rows rather
      than duplicating them (same "truncate and reload" policy as
      `load-genes`), so a corrected Colab re-run is safe to re-ingest.
      `sample_qc` also records `salmon_total_gene_assigned_counts` --
      AFED's own inclusion-gate numerator, see the QC note below -- even
      though the gate itself isn't enforced yet. `qc_status`/`quant_status`
      are left untouched (still genuinely unused everywhere in the
      codebase, per Milestone 4's own note); only `pipeline_status` drives
      `atlas status`. 9 new tests (100 total, all passing). Real run:
      ingested the 11 already-Colab-processed samples (DRR059464/65/66 +
      the 8 PRJNA121091 runs), correcting their `pipeline_status` from
      stale `APPROVED`/`RETRY` values to `QUANTIFIED`.
      `workflows/ingest_colab_drop.sh` (moves a Drive zip's accession
      folders into `results/<accession>/`) remains a separate, earlier step
      -- this command only reads what's already there.
- [ ] Not yet done: the QC-based inclusion gate for accepting a sample's
      quantification into the atlas -- see the AFED QC note below. Also not
      yet done: `DRR786485` (Milestone 5's original local-Nextflow sample,
      still `RETRY`) never got a Colab-shaped `results/DRR786485/` folder,
      so `process ingest` can't pick it up as-is; low priority, one sample.

## AFED's QC/inclusion criteria (for our own qc.yaml, not yet implemented)

Read AFED's actual `star_quantification.R` (not just the README) to answer
the user's question (2026-09-20) about what inclusion gate to use. AFED
keeps a sample (`samples_to_keep` in that script) only if **all** of:

- `total_counts >= 1e6` -- at least 1,000,000 total **gene-assigned**
  counts (STAR `ReadsPerGene.out.tab` summed, tRNA genes excluded first),
  not raw read count. This is a post-quantification gate, not a
  pre-download filter.
- not in `low_coding_samples` -- a list of samples flagged by Picard
  `CollectRnaSeqMetrics` (exact threshold not visible in this script; it
  reads a precomputed `output/picard/low_coding_samples.txt`) for a low
  fraction of reads landing in coding regions -- catches poor library
  prep / rRNA contamination / degraded RNA.
- not in `q30_below_75` -- fastp-reported samples with **less than 75% of
  bases at Q30+** quality.
- still present in the current SRA metadata pull (`run %in% sra_df$run`).

Separately (not a pass/fail gate, a correctness step): AFED classifies
each sample's strandedness from its own count distribution
(`frac_strand1 > 0.7` / `< 0.3` / else "unstranded") to pick the right
STAR count column -- worth doing the equivalent for Salmon's own
strandedness inference before trusting `--nf_core_rnaseq_strandedness auto`
blindly.

`nf-core/rnaseq` already runs fastp and can run Picard
`CollectRnaSeqMetrics`-equivalent QC as part of its own MultiQC report, so
these thresholds are directly adoptable into `config/qc.yaml` once
Milestone 5 produces a real QC report to calibrate against -- not
implemented yet.

## Feature idea: chromosome-wide TPM abundance map (IMPLEMENTED 2026-09-24 -- see Round 7 below)

User's idea (2026-09-21), for the eventual site/app: a window showing all
8 nuclear chromosomes of RIB40, colored by transcript abundance (TPM) per
genomic region, to visually spot high- and low-expression regions. Not an
AFED feature (docs/decisions/0002-afed-audit.md's audited interface has no
genome/ideogram view) -- an AOED-original addition. Closer in spirit to
the JBrowse ambition already flagged for Milestone 8 (PROJECT_MASTER_SPEC.md
section 37/40), but meaningfully lighter: it only needs gene-level Salmon
TPM + gene coordinates already in the database, not STAR alignment/BAM/
bigWig coverage tracks -- doesn't need to wait on
`quantification.secondary_route_star` at all. Best scheduled as a
Milestone 7-adjacent stretch feature once the basic interface exists to
host it.

**Data already available, no new pipeline work needed:**
- `genes.chromosome/start/end/strand` already has real coordinates for
  RIB40's 8 nuclear chromosomes. Checked 2026-09-21: `Chr1_A_oryzae_RIB40`
  through `Chr8_A_oryzae_RIB40`, 908-2048 genes each (gene density varies
  ~2.3x across chromosomes), plus 3 unplaced contigs and the mitochondrial
  genome with only 1-16 genes each -- too sparse to render meaningfully in
  an 8-chromosome karyotype; show those separately or omit rather than
  distorting the main view.
- `gene_expression.TPM` (long format, sample_id x canonical_gene_id) is
  already populated by `atlas process ingest` for every ingested sample.

**One real data gap:** chromosome *lengths* aren't in the database yet --
`genes` only gives the last annotated gene's end position per chromosome,
which understates true length (telomeric regions have no genes). The
actual lengths are sitting unread in
`database/FungiDB_v71/FungiDB-71_AoryzaeRIB40_Genome.fasta`'s sequence
headers; extracting them once (a small table or reference file, same spirit
as the existing Milestone 1/3 reference-loading tooling) is the only new
data-prep step this feature needs.

**Design decisions to make before implementing (deliberately left open,
not decided here):**

1. **Aggregation unit -- per-gene vs. fixed-size genomic windows.**
   Per-gene (color each gene's own footprint by its own TPM) is simplest
   and adds no invented parameter, but looks uneven/gappy given how much
   gene density varies by chromosome. Fixed windows (e.g. 10-50kb bins,
   the standard genome-browser-track convention) aggregate all genes
   overlapping each bin and read more like "regions", matching what the
   user described ("quantidade de transcrito por região"), at the cost of
   a tunable bin-size parameter. Leaning toward fixed windows, with the
   bin size configurable rather than hard-coded to one value -- same
   multi-threshold philosophy `config/qc.yaml` already uses for TPM
   detection thresholds, instead of silently picking one arbitrary size.
2. **Which TPM value drives the color.** TPM is inherently per-sample, so
   a single genome-wide map has to pick one of: a single selected sample;
   a condition-level mean (this is exactly why the Milestone 6 `conditions`
   curation, discussed the same day, matters beyond that milestone); or a
   whole-atlas mean/median as a default "landscape" overview. Likely a
   selector in the UI with whole-atlas mean as the default view -- a UI
   decision, doesn't block building the underlying binned-TPM computation
   now.
3. **Color scale.** TPM is long-tailed (0 to the thousands); a linear
   scale would make almost every region look identical. Use a log scale
   (log10(TPM+1)) against a perceptually uniform colormap (e.g. viridis),
   and give TPM~0 regions a visually distinct "not detected" treatment
   instead of just the bottom of the gradient.
4. **Layout.** A true karyotype layout (8 bars, each drawn proportional to
   its real chromosome length) is more honest than 8 equal-width panels,
   since chromosome extents differ by >2x (Chr1's genes span to ~6.5Mb,
   Chr7's only to ~2.9Mb; real lengths from the FASTA will run a bit
   longer). Needs the chromosome-length data gap above closed first.
5. **Interaction.** Hovering/clicking a region should surface the actual
   genes there, linking into the per-gene search Milestone 7 already
   plans -- a color-only view with no drill-down loses the "which gene is
   that" payoff that's the actual point of the feature.

**What was actually built (2026-09-24), answering the 5 open decisions above:**

1. **Fixed windows**, not per-gene -- 50kb default, a `bin_size_bp`
   parameter on `genome.karyotype.bin_gene_expression`/
   `webexport.build.export_chromosome_expression` (not yet a CLI flag;
   trivial to expose one if a different bin size is ever wanted).
2. **Whole-atlas median TPM**, no per-sample/per-condition selector: reuses
   `gene_expression_behavior_established.parquet`'s `median_TPM` (median
   across every curated condition -- the same "whole atlas" value the
   classification pie chart's Tau is computed from), matching the user's
   explicit "com todos os dados" framing. A selector (single sample /
   single condition) is a real follow-up, not built here.
3. **log10(mean TPM + 1)**, one hue (blue, the same sequential ramp
   anchor as `--accent`/`--series-1`) light->dark -- `--seq-100..--seq-600`
   in `tokens.css`. Bins with zero annotated genes get a visually distinct
   muted fill (`--surface-sunken`), never the ramp's own lightest step --
   "nothing measured here" and "measured near-zero" must not look the
   same.
4. **True karyotype layout**: all 8 chromosome tracks share one
   pixels-per-bp scale, so Chr7 (2.9 Mb) visibly reads shorter than Chr1
   (6.5 Mb). The "one real data gap" this section flagged (chromosome
   lengths not in the database) turned out to already be closed --
   `reference/genome_fasta.py`'s `load_genome_sequence_lengths` already
   existed (Milestone 3 reference validation) and was reused as-is, no new
   FASTA parsing written.
5. **Hover + click-to-drill-down**, entirely client-side: the exported
   JSON only carries per-bin aggregates (760 bins total, ~29KB), not a
   gene list per bin -- hovering a bin filters the already-loaded full
   gene catalog (`data/realGenes.ts`) by chromosome + midpoint inside the
   bin's range and previews the top few by the classification table's
   `median_TPM`. **Updated 2026-09-24** per user feedback: clicking a bin
   no longer jumps straight to that one top gene -- it opens the exact
   same ranked-bar-chart component the home page's main "genes by total
   expression" view uses (`GeneRankingChart`, reused as-is via
   `lib/points.ts`'s `buildGeneRankings`), scoped to just that window's
   genes, with a "back to chromosome map" control. Still entirely
   client-side, no new backend endpoint.

New code: `src/aoryzae_atlas/genome/karyotype.py` (+ `tests/
test_genome_karyotype.py`), `webexport.build.export_chromosome_expression`
(writes `app/web/public/data/chromosome_expression.json`, part of `atlas
app export-web` / `atlas refresh` -- no separate command), `app/web/src/
components/overview/ChromosomeExpressionMap.tsx`. Still not built: a
sample/condition selector, and the JBrowse-track convergence the GDV entry
below describes -- this stays a standalone lightweight view for now, not
merged into a genome browser.

## Feature idea: GDV-style genome browser (not yet scheduled)

User's idea (2026-09-21): a real genome browser in the site/app -- search
by sequence/gene/location, browse tracks -- modeled on NCBI's Genome Data
Viewer for our own reference assembly
(https://www.ncbi.nlm.nih.gov/gdv/browser/genome/?id=GCF_000184455.2 --
**GCF_000184455.2 is the exact assembly Milestone 3 already verified
matches our RIB40 FASTA byte-for-byte on total length**, so GDV's view of
"our" genome is a direct preview of the real thing), plus more than GDV
itself offers. This is the same PROJECT_MASTER_SPEC.md section 37/40
"JBrowse" ambition already flagged for Milestone 8 -- this entry is the
concrete design pass for it, prompted by GDV as a reference point.

**What I checked in GDV itself (2026-09-21) to ground this, not guesswork:**
- Its ideogram sidebar lists `MT, 1, 2, 3, 4, 5, 6, 7, 8` plus "Unplaced/
  unlocalized scaffolds: 3" -- exactly our own 8 chromosomes + 3 unplaced
  contigs + 1 mitochondrial genome (Milestone 3), same numbers, confirming
  again it's the same assembly.
- Chr1 reports as `1-6,520,266` bp -- matches our `genes` table's Chr1 max
  gene end (6,510,551) closely, real length is a little past the last
  annotated gene as expected (see the chromosome-length gap in the TPM-map
  idea above -- both features need the same missing chromosome-lengths
  data).
- Core UI: a "Location, gene or phenotype" search box; a clickable
  ideogram chromosome selector; a scrollable/zoomable gene track ("Genes,
  RefSeq propagation from INSDC submitter") with an exon-level view that
  only activates once the visible region is narrow enough ("too many
  genes in region" otherwise); a Tracks menu with **Configure Tracks**,
  **Configure Track Hubs**, **NCBI Recommended Track Sets**, and **My NCBI
  Track Collections** -- i.e. a real multi-track, user-extensible
  architecture, not a fixed single view; a BLAST panel; a navigation
  History panel.
- Searching our own FungiDB canonical ID (`AO090001000001`) in GDV's
  search box did **not** resolve to a location -- RefSeq's own annotation
  of this assembly uses its own locus tags/gene symbols, not FungiDB's
  AO09 identifiers. Concretely: **we cannot just proxy search to GDV/
  RefSeq** -- our search has to run over our own `genes`/
  `gene_external_identifiers` tables (the very cross-reference work
  Milestone 1 already built) and only use RefSeq/GDV data for the
  sequence/track rendering underneath.

**Proposed technical backbone: JBrowse 2**, not a from-scratch canvas/D3
browser -- consistent with the project's own stated preference (spec
section 0/9/29) for reusing established, pinned tools over ad hoc
scripting, and already the tool `config/pipeline.yaml`'s
`secondary_route_star` flag was left in place for ("only enabled
explicitly for JBrowse/coverage needs"). JBrowse 2 gives us for free what
would otherwise be the hard part: a maintained, embeddable
(`@jbrowse/react-linear-genome-view` or similar) pan/zoom track renderer,
native GFF3/FASTA/BigWig/BAM support, and a real plugin system for custom
track types -- which is exactly the hook the chromosome-TPM-abundance-map
idea (above) needs. That idea shouldn't be built as a separate standalone
viewer; it should be **one JBrowse track type** (a custom renderer reading
binned TPM instead of coverage depth), so the two feature ideas from this
same conversation converge into one browser instead of two.

**Concrete data-prep steps this needs (all from files we already have,
no new sequencing/pipeline work):**
1. Index the existing genome FASTA (`database/FungiDB_v71/
   FungiDB-71_AoryzaeRIB40_Genome.fasta`) for random access (`samtools
   faidx` + a `.2bit` or bgzip+`.fai`, whichever JBrowse 2's reference
   track wants).
2. Sort + bgzip + tabix-index the existing GFF3 (`FUNGIDB_GFF_FILE`) into
   a JBrowse-servable gene-model track -- this is the same annotation
   Milestone 1/3 already parsed into `genes`/`gene_master.tsv`, so gene
   names/IDs shown in the browser track and in the rest of the app stay
   the same canonical IDs.
3. Extract real chromosome lengths from the FASTA headers (same gap noted
   in the TPM-map idea -- one extraction serves both features).
4. Our own backend search endpoint over `genes` + `gene_external_identifiers`
   (AO09 ID, gene symbol, alias, or `Chr:start-end` location), returning a
   locus JBrowse can navigate to (`navToLocString`-equivalent) -- not GDV's
   search, per the finding above.

**Open questions, deliberately not decided here:**
- **Multi-strain support.** Per the cross-strain scope decision above
  ("Sample curation" section, 2026-09-20): AOED's sample scope already
  spans strains beyond RIB40, but a genome browser needs an actual
  reference sequence + annotation per strain shown -- GDV only ever shows
  one fixed NCBI assembly. Whether/how to browse a non-RIB40 strain
  (a different reference entirely, or read-mapping non-RIB40 samples
  against the RIB40 track by homology) is unresolved and probably shouldn't
  block a first RIB40-only version.
- **BLAST-style sequence search.** GDV has one; meaningfully bigger lift
  (a BLAST index + a query service) than the rest of this feature. Treat
  as a stretch add-on, not part of a first version.
- **How much exon/isoform detail to expose.** GDV gates exon-level
  rendering behind a minimum zoom level for performance; our own gene
  models (FungiDB v71 GFF) need the same check before assuming full detail
  renders cheaply at whole-chromosome zoom.
- **"More than GDV"**: the user explicitly wants to go beyond GDV's own
  feature set but didn't specify what yet, beyond the TPM-track
  convergence above -- revisit once there's a first working browser to
  extend, rather than speculating further now.

## Feature idea: gene expression classification, shown as a homepage pie chart (IMPLEMENTED 2026-09-24 -- see Round 7 below)

User's idea (2026-09-21): classify every gene from the global expression
analysis into classes -- high expression, low expression,
condition-specific expression, constitutive-low, and others -- and
surface that classification as a pie chart on the site's home page. The
user explicitly flagged that Tsallis entropy (discussed earlier as a
project component) is the tool they had in mind for this, and was equally
explicit that **nothing about the actual classification scheme is decided
yet** -- this entry records the idea and where it plugs into the plan
that already exists, not a new scheme invented here.

**This isn't a new analytical idea -- it's already deeply specified.**
`PROJECT_MASTER_SPEC.md` sections 16-21 (Milestones 9-11: gene statistics,
Tsallis/Hill, clustering) already lay out exactly this, in real detail:

- Section 16: per-gene Tsallis entropy `S_q` and Hill/effective-diversity
  number `D_q` across samples or conditions, at multiple `q` values
  (0.5/1/2/3/4 by default, arbitrary `q` must be supported) -- **and an
  explicit warning that high entropy must never be auto-labeled
  "housekeeping"**: a gene can be broadly distributed but very low
  abundance, so classification must jointly weigh abundance, prevalence,
  variability, diversity, *and* condition enrichment together, not
  diversity alone.
- Section 17: compute this at **both** sample level and condition level in
  parallel (never only sample level) -- with 11 samples currently split
  across 3 studies, a handful of heavily-sampled conditions could
  otherwise dominate a gene's apparent "diversity" purely from sampling
  imbalance, not biology.
- Section 18: benchmark Tsallis/Hill against at least one classical
  specificity metric (e.g. Tau) plus prevalence/robust-CV -- not trusted
  alone.
- Section 19: **classification must start from unsupervised clustering**
  on a proper feature table (log1p(median TPM), prevalence, robust CV,
  Tau, `D_0.5..D_4`, a dynamic-range measure), validated (silhouette,
  BIC/stability-under-resampling, sensitivity to both the TPM detection
  threshold and to `q`) -- explicitly **not** hand-picked thresholds as a
  first approach.
- Section 20: human-readable labels (`constitutive_high`,
  `constitutive_medium`, `constitutive_low`, `variable`,
  `condition_specific`, `inducible_high`, `rarely_expressed`,
  `broad_low_expression`) are assigned only *after* clusters prove stable,
  and are explicitly provisional. The computational `cluster_id` (e.g.
  `GMM_04`) must always be stored alongside and never overwritten by the
  label. A `housekeeping_candidate` flag is separate again, requiring
  supporting functional evidence, not expression behavior alone.
- Section 21: gene-to-condition summaries (`gene -> conditions with
  highest/lowest expression`, `condition -> constitutive genes`,
  `condition -> induced genes`) round this out.

**What's genuinely new here vs. the existing spec:** the homepage pie
chart itself -- a specific site/UX placement the spec doesn't dictate.
Design implications worth noting now, before it's built:
- A pie chart needs a small number of coarse, legible buckets -- the
  section-20 label set (or a further-collapsed version of it) is the
  right shape for this, not raw per-gene metrics.
- It has to be **precomputed and cached**, not calculated live per page
  view -- this is a whole-atlas, whole-gene-set clustering pass (12,090
  genes x every ingested sample/condition), not a per-request query.
  Fits naturally as a scheduled/triggered job that (re)writes a small
  summary table (`gene_id -> cluster_id, biological_label`) for the
  frontend to read, refreshed as new samples/conditions get ingested
  rather than recomputed on every visit.
- It lands on the same home view the Milestone 7 frontend spike below
  already built (`app/web/` -- currently a "genes by total expression"
  ranking as the default screen) -- this pie chart is a second homepage
  chart alongside that one, not a replacement.

**Why this shouldn't start yet:** clustering 12,090 genes across only 11
ingested samples spanning 3 small studies would produce classes driven by
sampling noise, not biology -- the spec's own sensitivity/stability checks
(section 19) would likely fail outright at this sample size. Realistic
trigger to revisit: once Milestone 6 (replicated-condition curation) and
several more Colab batches land, giving enough samples/conditions for
condition-level entropy (section 17) to mean something.

**Built anyway, 2026-09-24, on explicit user instruction** ("por enquanto
temos poucas classificações... mas lembre de por no TODO"): the user
wants to see it now, at pilot scale, understanding it's provisional --
not a reversal of the caution above, an explicit choice to accept it. What
shipped:

- A **donut**, not a plain pie -- same part-to-whole read, but the center
  hole carries the total classified-gene count (a stat-tile-style hero
  number), and it's what the dataviz skill's form guidance favors over a
  bare pie once there's a natural headline number to show. Colors are the
  existing fixed-order categorical slots (`--series-1..5`); the
  `biological_label` set has 5 possible values (`constitutive_high/
  _medium`, `variable_broad`, `condition_specific`, `rarely_expressed`)
  mapped to slots 1-5 in that fixed order regardless of which are actually
  populated in a given run -- at K_BASE=2 (current pilot scale) only 2
  light up, more appear automatically as clustering resolves more groups
  with no code change. Genes with no label (<2 detected conditions, Tau
  undefined) get a 6th, deliberately **muted gray** slice ("Not enough
  data yet") rather than a 6th vivid hue -- it isn't a biological category.
- Explicit **preliminary/provisional framing in the UI itself**, not just
  here: the chart's own subtitle says "Preliminary: based on the atlas's
  current sample/condition coverage and will sharpen as more studies are
  added" -- so a site visitor isn't misled into reading 2-cluster K_BASE
  as a finished biological result.
- Hover shows count + percentage; clicking a slice or legend row opens
  that category's highest-median-TPM gene (same "give the drill-down a
  concrete landing spot" pattern as the chromosome map below), entirely
  client-side from data already loaded -- no new backend endpoint.
- **Not built**: Tsallis/entropy is NOT what actually drives this
  classification (the notebook's own Part B conclusion, Round 6, found
  the q-spectrum adds no clustering value and hurts stability) -- the pie
  reflects the BASE model (Tau + abundance/prevalence/variability) the
  user originally flagged Tsallis for, just via the metric that actually
  won out after real testing, not the one guessed at when this idea was
  first written down. No click-to-filter-the-rest-of-the-page yet (e.g.
  filtering the ranking chart to just `condition_specific` genes) -- a
  real follow-up once there's a natural place to route that filter state.

New code: `app/web/src/lib/classificationSummary.ts` (pure, slice/color/
order logic), `app/web/src/components/overview/ClassificationPieChart.tsx`.
No backend change -- reads the same `classification.json`
`atlas cluster genes` already produces (Round 6).

## Milestone 7 spike: gene search + expression UI (2026-09-21, not a milestone completion)

Started ahead of Milestone 7's formal gate (Milestones 1-6 aren't all
validated yet), at the user's request, to do the UX/product design work
for the AOED interface while it's fresh. Resolved ADR 0002's deferred
"Shiny vs. Python-native" question: **React + TypeScript + Vite**, not
AFED's Shiny code -- see `docs/decisions/0005-milestone7-frontend-stack.md`.
`app/aoed_shiny/` (empty placeholder) removed; lives in `app/web/` now.

Built: gene search (AO09/symbol/name/alias/UniProt), gene identity header,
per-sample TPM plot (grouped by condition, colored by study, linear/log10
toggle, QC-flagged samples marked by a dashed ring + icon+label badge, not
color alone), sample metadata table (sortable, CSV export), and a context
panel (gene-level summary stats, or per-sample metadata/QC on selection) --
MVP target items 4 and 11 from `PROJECT_MASTER_SPEC.md` section 24.
Not built yet: heatmap, PCA, the chromosome-TPM-map and genome-browser
ideas above.

Runs against `app/web/src/data/fixtures.ts` -- data shaped exactly like
the real DuckDB tables but with invented accessions/hand-tuned TPM values,
since the real atlas only has a handful of ingested samples so far. Needs
a real API/DuckDB fetch layer before this is the actual Milestone 7
deliverable, once Milestone 6 (multi-sample database) closes.

Node.js (LTS, via winget) is now a project dependency for this frontend.

**Round 2 (2026-09-21, same day):** per user feedback --
- New home view: a "Genes por expressão total" ranking -- every gene,
  summed TPM across samples, sorted descending, stacked bar per gene
  (segments = individual samples, colored by study). This replaced the old
  blank "search to begin" empty state as the app's default screen; clicking
  a bar drills into that gene's detail view (same screen as before). Linear
  scale only here deliberately -- a log scale on a *stacked* total would
  misrepresent segment proportions, so the toggle was left off this chart
  (kept on the per-gene chart, where each bar is an independent value).
- The per-gene expression chart (previously a dot/strip plot) is now a bar
  chart too, per request -- same grouping/color/interaction, QC-flagged
  samples now marked with a small warning-triangle glyph above the bar
  instead of a dashed ring (rings don't read on a bar mark).
- Both charts default to **all strains and all conditions**; strain and
  condition are now both optional top-bar filters that scope every chart,
  not just strain as before -- nothing gates on them.
- Added the LEBIMO lab logo (`app/web/src/assets/lebimo-logo.png`) to the
  top bar; it's also now a "go home" button. Source PNG has an opaque white
  background, so it'll show as a white box in dark mode -- fine for now,
  worth swapping for a transparent version later.

**Round 3 (2026-09-21, same day):** per user feedback --
- Logo enlarged (28px -> 48px tall; top bar 52px -> 68px) -- it read as too
  small to register as a real brand mark at the old size.
- UI copy switched from Portuguese to English throughout (labels, chart
  axis/legend text, tooltips, empty/loading states, aria-labels). Fixture
  data (`condition_label` and related `Condition` fields, gene names/
  descriptions) was already written in English, so no data changes needed --
  this was a component-string-only pass.
- New: every BioProject code shown anywhere in the app (chart legends,
  the sample table's Study column, the right panel's sample-detail view)
  is now a click target (`src/components/common/DatasetLink.tsx`) that
  opens that study's full record in the right panel -- publication title,
  DOI, organism/strain, design description, sample/condition counts, all
  pulled straight from the existing `datasets` fixture table (no new data
  needed). Deliberately did **not** turn the DOI into a live external link:
  fixture DOIs are invented placeholders, and a fake DOI resolving to some
  unrelated real paper would be actively misleading -- revisit once
  Milestone 6 lands real publication metadata.

**Round 4 (2026-09-21, same day):** per user feedback -- logo fix, and
loading the real full genome to stress-test UX/UI at scale.
- Logo fix, properly this time: the *real* bug in Round 3 wasn't size --
  the source PNG had a huge transparent margin around the actual LEBIMO
  mark (content bounding box only 1074x295 of the 1920x1080 canvas), so
  `height: 48px` was scaling mostly empty space; the visible mark rendered
  at ~13px regardless of the CSS height. Cropped the PNG to its alpha
  bounding box (`app/web/src/assets/lebimo-logo.png`, +12px pad) so the
  CSS height now controls the actual visible logo size.
- Loaded the real 12,090-gene RIB40 catalog (`metadata/gene_master.tsv` +
  `metadata/gene_external_identifiers.tsv`) into the app, merged with the
  9 curated hero genes, to see how the UI holds up at real genome scale --
  exactly what the user asked to test. New:
  `app/web/scripts/export_gene_catalog.py` (stdlib csv/json, no pandas
  dependency) joins the two TSVs per gene and writes
  `app/web/public/data/genes.json` (~3MB, gitignored -- reproducible,
  regenerate after pulling changes to those TSVs or on a fresh clone, see
  `app/web/README.md`). Fetched at runtime (`src/data/realGenes.ts`), not
  bundled, so the JS bundle stayed ~270KB. Genes outside the 9 curated
  ones get deterministic synthetic filler TPM
  (`src/lib/syntheticExpression.ts`, log-spread baseline + per-sample
  noise + a detection-probability dropout so lowly-expressed genes aren't
  "detected" in every sample) -- no biological story, purely for
  rendering/interaction load, since real full-genome quantification
  doesn't exist yet. `Gene` gained `uniprot_accession`/`fungidb_alt_id`/
  `aliases` fields (folded the old separate `GeneExternalIdentifier[]`
  array into the gene record itself -- simpler and smaller now that it's
  12k+ rows instead of 9).
- Real data exposed a real gap the 9-gene fixture had hidden: only ~5% of
  genes have a curated short symbol (706 `gene_alias` rows out of 12,090);
  the rest fall back to the UniProt protein-name field (97.6% coverage) or
  the bare AO09 ID. Added `src/lib/geneDisplay.ts`
  (`primaryGeneLabel`/`isSymbolicLabel`) so headers, search results, and
  chart labels use that fallback chain and never italicize a non-symbol
  label (italics is a nomenclature convention for real symbols, wrong for
  an ID or a full protein-name sentence). ~21% of genes are literally
  named "Uncharacterized protein" (real FungiDB/UniProt annotation state,
  not a bug) -- expect repeated-looking labels on the ranking chart;
  hover/click always disambiguates by ID.
- UX problems the scale test actually surfaced, and what was done:
  - Ranking chart: capped to the top 40 genes by total (of 12,099), with
    a "Top 40 of N" label and a nudge to use search for anything else --
    rendering or even just labeling all 12k as bars was never going to be
    legible. Per-bar total-value text labels (fine at 9 genes) collided
    into unreadable overlapping text at 40 -- removed them except on the
    single highest bar, moved the total into the hover tooltip instead
    (the dataviz skill's "label selectively" rule -- direct labels stop
    working once flooded). Bottom-axis gene labels now rotate -50deg and
    truncate to 16 chars (were horizontal and unbounded, fine for 9 short
    symbols, illegible for 40 long UniProt names).
  - Search stays fast at 12k genes (single-digit ms typical, ~120ms
    measured worst case for a common substring like "kinase" including
    React re-render) -- no debounce added, but worth revisiting if typing
    ever feels laggy on a slower machine.
  - Filter-driven ranking recompute is sub-millisecond even across all
    12,099 genes (confirmed with the tab actually focused/visible --an
    initial reading of 2+ real seconds, and later a 45s timeout, turned
    out to be `requestAnimationFrame`-based test timing measured against
    a backgrounded browser tab, which Chrome throttles/pauses; not a real
    app slowdown. Recording this so it isn't mistaken for a regression
    and re-investigated later -- always re-measure with the tab focused.

**Round 5 (2026-09-21, same day):** per user feedback -- gene length, and
a user-adjustable "how many genes" control for the ranking chart.
- Gene length now shown wherever gene identity appears: a `Length` row in
  the right panel's Identity section, and a `X,XXX bp` tag next to
  `protein_coding` in the gene detail header
  (`src/lib/geneDisplay.ts`'s `geneLengthBp`/`formatBp`, `end - start + 1`,
  genomic coordinates are 1-based inclusive).
- The ranking chart's gene count is now a user control (a "zoom" slider,
  `src/components/overview/GeneRankingOverview.tsx`) with log-ish preset
  steps -- 10 / 25 / 40 (previous fixed default) / 100 / 250 / 500 / 1000
  / 2500 / 5000 / All (12,099) -- rather than a fixed top-40 cap.
  Confirmed the user's own instinct that this needs two different
  renderers, not one chart straining to cover both ends:
  - **<=60 genes ("labeled")**: unchanged from before -- per-sample
    stacked segments, rotated truncated gene labels, individual
    hover/click/keyboard-nav per bar.
  - **>60 genes ("dense")**: per-gene labels and per-sample segments both
    stop being legible or cheap to render, so this switches to one
    aggregated (per-study, not per-sample) `<path>` **per dataset color**
    covering every bar -- 3 DOM path elements regardless of whether it's
    100 genes or all 12,099 (confirmed: still ~190ms to switch to "All"
    and re-render, 3 `<path>`s in the DOM either way). No per-gene x-axis
    labels at this density (replaced with numeric rank ticks -- #1,
    #3,026, ... -- since "Rank" is what the x-axis actually encodes once
    individual identity can't be labeled); hover/click use a single
    crosshair overlay that resolves the nearest gene by x-position
    (dataviz skill's line/area hover pattern) instead of one hit-target
    per gene, with arrow-key support for keyboard users. At full density
    the stacked bars visually merge into a continuous silhouette -- this
    is a legitimate rank-abundance/Whittaker-plot form (common in
    ecology/genomics for exactly "value vs. rank" data), not a rendering
    failure, and it's still genuinely informative: the dataset color
    composition visibly shifts across the expression-rank spectrum.
  - Deliberately kept the dataset legend visible at every zoom level
    (the user's own message anticipated it might need to disappear at
    "All") -- since dense mode still colors by (aggregated) dataset, the
    legend stays meaningful throughout rather than becoming dead chrome;
    called this out rather than silently overriding the suggestion.

**Round 6 (2026-09-22): the DB -> web "bridge" -- `atlas refresh`.** User
had been growing the real database directly (new Colab-ingested samples,
curated `metadata/conditions.tsv`/`samples.tsv`, and a notebook-driven
gene-expression classification pass -- `notebooks/gene_expression_
classification.ipynb` / `reports/gene_expression_classification.md`) with
no path from any of that into the website, and asked for a single
standardized command to run after every future data addition. This round
turns four previously-stubbed CLI command groups into real, tested
pipeline steps and adds a new one, chained by `atlas refresh`:

    atlas database migrate/load-genes/load-discovery/load-conditions
      -> atlas process ingest --all
      -> atlas matrix build          (NEW: real, was a stub)
      -> atlas stats genes           (NEW: real, was a stub)
      -> atlas entropy genes         (NEW: real, was a stub)
      -> atlas cluster genes         (NEW: real, was a stub)
      -> atlas app export-web        (NEW command)

- `src/aoryzae_atlas/clustering/classify.py` (new): a faithful, unit-tested
  extraction of the notebook's Section 11/13/24 decisions (KMeans, k
  selected by silhouette over k=2..10, the same cautious threshold-based
  `biological_label` rule) into reusable code -- `atlas cluster genes` now
  reproduces the notebook's exact pilot-run numbers (K_BASE=2,
  constitutive_high/condition_specific/unlabeled counts matched exactly in
  a same-day comparison run). Deliberately does NOT reproduce the
  notebook's EXTENDED (Tsallis q-spectrum) model or its cluster-stability
  diagnostics (subsampling/bootstrap/leave-one-study-out ARI, dendrograms,
  pairplots) -- the notebook's own Part B conclusion was that the
  q-spectrum adds no clustering value and *hurts* stability, so the
  automated pipeline doesn't pay that cost on every run; stability
  diagnostics stay a deliberate, occasional notebook exercise, not
  something re-run on every sample addition. `atlas cluster genes` writes
  its own short summary (`reports/gene_expression_behavior_summary.md`)
  and leaves the notebook's deeper methodology writeup untouched.
- `src/aoryzae_atlas/webexport/build.py` (new) + `atlas app export-web`:
  reads DuckDB (only samples that are QUANTIFIED **and**
  condition-curated -- `CURATED_QUANTIFIED_FILTER`, so a sample mid-review
  never appears on the site) and the classification parquet, and writes
  `app/web/public/data/{datasets,conditions,samples,sample_qc,expression,
  classification}.json`, plus re-running `export_gene_catalog.py` for
  `genes.json` -- one command regenerates every JSON the frontend fetches.
  `qc_status` (pass/warning/fail) and `mapping_rate` are NOT pipeline-
  reported fields yet (only raw fastp/Salmon metrics are in `sample_qc`),
  so both are clearly-documented derived heuristics/proxies in
  `webexport/build.py` -- revisit once real QC gating exists.
- Frontend (`app/web/`): **dropped the fixture dataset entirely** --
  `data/fixtures.ts` now holds only the `referenceVersion` constant (the
  FungiDB annotation build, a different concept from a sample's own
  `reference_version`/quant-index label -- see the file's docstring). The
  9 hand-tuned "hero" genes from Rounds 1-5 were confirmed fictional
  (AO09-*format*, not real RIB40 loci -- see the old fixtures.ts comment),
  so keeping them mixed into a now-real-data app would have been actively
  misleading. New `src/data/realAtlas.ts` (`loadRealAtlas()`) fetches the
  six JSON files above at runtime, same pattern as `realGenes.ts`. `App.tsx`
  now runs entirely on this real data: 12,090 real genes, and (at this
  round's pilot scale) 41 real samples / 17 real conditions / 4 real
  studies / ~495k real expression rows / ~12.1k classified genes -- verified
  end-to-end in the browser (ranking chart, per-gene detail, sample table,
  QC badges, dataset detail panel, dense-mode "All genes" zoom). Added a
  lightweight "Expression behavior" block to the gene right panel
  (category / Tau / confidence) so the new classification data is visible
  now that it exists -- deliberately minimal, since the user said they'd
  design the fuller homepage treatment themselves later.
- `atlas refresh` skips (not fails) any step whose input isn't on disk yet
  (e.g. no `reports/discovery/*.tsv` before a first `atlas discovery
  report`), so it's always safe to run and always does as much as it
  currently can. Every step re-reads current on-disk/DB state, so it's
  safe to re-run repeatedly as more studies are added -- confirmed live
  during this round: the database was being actively grown by the user's
  own concurrent process while this was built (sample count changed
  between two `atlas refresh` runs minutes apart, migrate briefly hit a
  Windows file-lock from that concurrent writer), and a plain re-run
  picked up the new state cleanly with no manual intervention.
- Known follow-up, not done here: `expression.json` is ~19-20MB
  uncompressed at 41 samples x 12,078 genes (long format, one row per
  sample x gene) -- fine for local/dev use and consistent with
  `genes.json`'s existing runtime-fetch pattern, but will need either
  server-side gzip, a coarser aggregate-only payload for the ranking view,
  or a real per-gene API before this scales to hundreds of samples.

**Round 7 (2026-09-24): two homepage charts from the classification/genome data.**
User asked for both ideas already on file above -- the classification pie
chart and the chromosome-wide TPM abundance map -- built now, explicitly
accepting that the classification is still pilot-scale/provisional (user's
own words). Both sections above now carry full "what was actually built"
notes; this entry is the cross-cutting summary.

- Both charts live directly below the gene-ranking overview on the home
  page, in the order requested: ranking chart -> classification donut ->
  chromosome map.
- New backend: `src/aoryzae_atlas/genome/karyotype.py` (fixed-window
  binning, tested) and `webexport.build.export_chromosome_expression`,
  wired into the existing `atlas app export-web`/`atlas refresh` bridge
  from Round 6 -- no new CLI command, no new manual step. The
  classification pie chart needed **no backend work at all**: it's a pure
  client-side aggregation of the `classification.json` Round 6 already
  produces.
- Followed the dataviz skill's procedure for both: form choice before
  color (donut over a bare pie once there's a natural center number;
  sequential one-hue ramp for the chromosome map's magnitude encoding, not
  a rainbow), reused the project's already-validated categorical palette
  for the donut rather than re-running the validator (no new categorical
  palette was introduced), and added a new sequential ramp
  (`--seq-100..--seq-600`, light and dark) to `tokens.css`, anchored on
  the same blue as `--accent`/`--series-1` per the skill's reference
  palette.
- Both new sections degrade gracefully (a plain "not yet available, run
  `atlas cluster genes`/`atlas stats genes`" message) if their backing
  JSON is missing or `classification.json` was never generated -- same
  "None if not computed yet" pattern `export_classification` already
  established in Round 6, extended to `export_chromosome_expression`.
- Verified end-to-end in the browser, light and dark: donut renders with
  real counts (7,542 / 3,344 / 1,192 at this round's pilot scale),
  chromosome map renders all 8 real chromosome tracks at true relative
  length (760 bins, ~29KB), hover tooltips resolve real genes in real
  bins, and clicking either chart's data points a lightweight regions/
  categories -> a concrete gene drill-down, landing on the correct gene
  detail view with the correct classification badge every time.
- Environment note, unrelated to any code change: a stale
  `%LOCALAPPDATA%\Temp\pytest-of-bruno` directory became unreadable
  (`PermissionError`, even via PowerShell `Remove-Item`) partway through
  this round, breaking any test using pytest's `tmp_path` fixture.
  Worked around with `pytest --basetemp=<scratch dir>` rather than fighting
  the ACL; if this recurs, it's an OS/antivirus-level lock on that specific
  folder, not a code regression -- the same `--basetemp` workaround
  should unblock it again.

**Round 7 follow-up (2026-09-24, same day), per user feedback right after
seeing it:**
- Chromosome map switched from horizontal rows to **vertical columns**
  (8 chromosomes side by side, true relative height, tallest = Chr1 at
  480px) -- reads more like a conventional karyotype/ideogram. The
  low->high + "no annotated genes" legend moved from above the diagram to
  below it.
- Clicking a 50kb region no longer opens a single gene. It now opens the
  **same `GeneRankingChart` component the home page's main ranking chart
  uses** (stacked-by-study bars, most to least expressed), scoped to only
  that window's genes via `lib/points.ts`'s existing `buildGeneRankings` --
  literally the same function and component, just called with a
  chromosome-position-filtered gene list instead of the full catalog. A
  "back to chromosome map" control returns to the karyotype view. Also
  respects the top bar's current strain/condition filters, same as the
  main chart.

**Round 7 second follow-up (2026-09-24, same day):**
- Default bin size **50kb -> 100kb**
  (`genome.karyotype.DEFAULT_BIN_SIZE_BP`) -- user felt 100kb reads more
  informative (fewer, more visually distinct bands). 760 bins -> 382 at
  the current pilot scale (~15KB exported, down from ~29KB). Still a
  parameter, not hard-coded logic -- one-line change, no new plumbing.
- **The legend is now an expression-level filter.** Each of the 5
  sequential-ramp swatches is a toggle button: clicking one dims every
  bin outside that exact color bucket (opacity 0.12, not hidden -- the
  karyotype shape stays visible for spatial context) across all 8
  chromosomes at once; clicking the same swatch again, or the new "Show
  all" link that appears next to the legend while filtered, clears it.
  The "no annotated genes" swatch is a filter toggle the same way. Made
  possible by pulling the bucket-index math out of `lib/sequentialColor.ts`
  into an exported `sequentialColorIndex()` used by both the paint step
  and the filter check, so the legend can never drift from what's
  actually drawn (a swatch's meaning is a real, computable predicate, not
  a description of one).

## Pan-transcriptomic expression rank (2026-10-02) -- notebook v2, see docs/decisions/0006

Re-did `notebooks/gene_expression_classification.ipynb` from the "global expression behavior across all
samples" brief (no per-study DE, no condition reconstruction, Tsallis dropped from the active path).

- [x] `src/aoryzae_atlas/rank/` (metrics, scores, classes, diagnostics, validation), `matrix.build.collapse_to_biosamples`,
  `tests/test_rank.py` (170 tests pass overall). Unit = biosample; every threshold is a run-time quantile
  (`derive_thresholds`), saved to `analysis/classification/gene_expression_rank_thresholds.tsv`.
- [x] Output `analysis/classification/gene_expression_rank.parquet` / `.tsv.gz` (44 columns: metrics, 4 scores,
  `expression_class`, `global_expression_rank` + 5 other orderings, `study_dominance`, `quality_flags`),
  `matrices/tpm/gene_by_biosample_TPM.parquet`, figures `analysis/descriptive/rank_*.png`, report
  `reports/gene_expression_classification.md` (regenerated by the notebook).
- [x] **Re-runnable + wired to the web app (2026-10-02).** `src/aoryzae_atlas/rank/pipeline.py`
  (`build_expression_rank`) is the single entry point: `atlas rank genes` writes the table/thresholds/summary,
  `atlas refresh` runs it before `app export-web`, the web bridge exports `expression_rank.json`, and the notebook
  ends with a consistency check that fails if its table differs from the pipeline's. **After adding data: run
  `atlas refresh`** (and re-run the notebook only if you want the figures/report regenerated). **If the pipeline
  logic changes, change it in `rank/pipeline.py` / the `rank/*` modules** -- the CLI and the site pick it up on
  the next refresh and the notebook check tells you when the notebook is out of date.
- [x] Homepage "Global expression behavior" (`ExpressionRankSection`): class bars (shared click-to-highlight),
  level x stability density map (canvas, hover/click opens the gene), top genes with six switchable orderings,
  classes per chromosome; gene panel gets the class, four score bars, rank and quality flags. The legacy
  condition-level donut is still the fallback when `expression_rank.json` is missing, and the gene panel keeps
  its condition-level clustering block (relabelled "preliminary") -- remove it once nobody needs the comparison.
- Findings worth carrying forward: the atlas is strongly structured by strain/study (~70% of genes have >= 80%
  of their highest-expression samples in one strain, almost always RIB40) and part of that is compositional
  (engineered-strain transcriptomes are dominated by a few very high genes); a composition-robust normalization
  is the next methodological refinement. Class retention is lowest when the RIB40/engineered-strain divide is
  split. Re-run the notebook unchanged as studies are added.

## Gene co-expression network (2026-10-14) -- see docs/decisions/0008

AFED-style co-expression ("which genes co-vary with this gene or gene set, and what do they have in common?"),
adapted to the multi-study atlas. Notebook: `notebooks/coexpression_network.ipynb` (Question/Answer/Conclusion per
section; every calculation is a call into `aoryzae_atlas.coexpr`).

- [x] `src/aoryzae_atlas/coexpr/` (`network.py`, `enrichment.py`, `pipeline.py`), `matrix.build.fetch_biosample_depth`,
  `tests/test_coexpr.py` + `tests/test_coexpr_pipeline.py` + CLI tests (all tests pass). Depth filter on
  `salmon_total_gene_assigned_counts` summed per biosample (default 10 M = AFED, `--min-reads-millions`), genes with
  mean TPM >= 1, two modes on the same genes (`all_samples` = AFED-style; `within_study` = per-study centering),
  Spearman, top-50 neighbours per gene with `rank`, `r`, `reverse_rank`, `mutual_rank`, `bg_tail`,
  `within_study_median_r`, `n_studies_tested`.
- [x] `atlas coexpr build` (also step `coexpr build` in `atlas refresh`, ~1 min) writes
  `analysis/coexpression/{coexpression_neighbours.parquet, coexpression_enrichment.parquet,
  coexpression_benchmark.tsv, coexpression_summary.json}` and `matrices/coexpression/zscores_<mode>.parquet`.
  `atlas coexpr query GENE [GENE...]` answers a gene or a gene SET (ids or symbols; note `gene_symbol` is empty for
  every gene in the current database, so use canonical ids) with a GO enrichment of the result.
- [x] Per-neighbourhood GO enrichment (hypergeometric, BH across terms per gene, universe = annotated network genes,
  terms 5-500 genes) for every gene at once; calibrated against random gene lists in the notebook (section 8).
- [x] `go-basic.obo` downloaded (2026-10-14, user-approved) to `database/GeneOntology/` (release 2026-07-26, 16,272 terms,
  provenance + sha256 in `database/GeneOntology/PROVENANCE.md`; the payload is gitignored). `atlas coexpr build` now
  propagates annotations over is_a/part_of and names the terms; re-run `atlas coexpr build` after updating the file.
- [ ] **Web network view** (user wants this next): export the edge table (`network.select_edges`, mutual rank <= 2 as the
  starting cut -- the graph percolates into one giant component by 3-5), a mode switch, mutual-rank and within-study
  support sliders, gene-set query, enrichment panel. Add a community-detection layer on top of the same columns.
- [ ] Possible refinements: counts-based size-factor normalisation instead of TPM (TPM is compositional), a confidence
  interval for the functional benchmark, strain-aware centering where strains and studies are separable.
- Findings to carry forward: the depth cut-off did not improve recovery of known functional groups (benchmark has little
  power for lowly-expressed genes, so 10 M is kept as the conservative default); pooled correlation is dominated by
  study/strain structure (16 % of random pairs exceed |r| 0.5 vs 7 % after per-study centering), so r alone is a weak edge
  criterion and rank/mutual rank are used instead; the two modes favour different groups (machinery vs. secondary
  metabolism / secreted enzymes).
- Data note: some `samples.strain` values hold whole sentences (e.g. "The A. oryzae strain HacA-CA, a hacA in
  constitutively active ..."), which inflates the strain count (18) and makes strain-level analyses and labels noisy --
  worth normalising in `metadata/samples.tsv`.

## Curated gene sets and the secretome (2026-10-26) -- see docs/decisions/0010

User-supplied list of 1,235 secreted genes (SignalP 6.0 signal peptide + UniProt cell wall) imported as the first
curated gene set; an annotation overlaid on the expression classes, not a class.

- [x] `src/aoryzae_atlas/genesets/curated.py`, `atlas geneset import|list`, `metadata/gene_sets/secreted.*`
  (1,223 genes; 41 retired AO09 ids redirected through the vetted FungiDB map), `tests/test_genesets.py`.
- [x] `atlas coexpr build` enriches every neighbourhood in the curated sets (separate from GO); `atlas coexpr query` prints it.
- [x] Web: `gene_sets.json` via `atlas app export-web`; homepage "Show: All genes / Secreted only" toggle (classes stay
  derived from all genes) and a "Gene sets" row in the gene panel. Verified in the browser pane.
  2026-10-27: the toggle's state now lives in `App.tsx` and also restricts the top "Genes by total expression" ranking
  (subtitle says "secreted genes only"), not just the behavior section; the gene-count slider remembers "All" across the
  filter (a remembered count above the new total means "All", it no longer snaps to 10).
- [x] `notebooks/secretome.ipynb`: set vs expression classes (Context-Specific x3.7, Rare/Silent x1.95, Constitutive
  Core/High depleted), scores, top genes, flags, chromosome/adjacency, co-expression, sanity check against GO.
- [x] `sspB` = AO090038000546 (user, 2026-10-26; already a member as a direct id, so the set stays at 1,223 genes).
- [ ] **Needs the user:** `AO090011000795-A` (alias of a vacuolar gene, almost certainly a different locus: the UniProt entry is
  dipeptidyl-peptidase 5). Add with `atlas geneset import secreted ... --map AO090011000795-A=<AO09 id>` once known.
- [ ] Re-run `notebooks/secretome.ipynb` (its Section 1 text and the limitations still say two ids were pending).
- [ ] **Would sharpen the set:** the per-gene evidence (SignalP-positive list and UniProt cell-wall list separately) to
  split "secreted / cell wall / both"; a look at the review list in the notebook (27 members annotated only to
  intracellular compartments) and at the 32 genes reached through retired ids (only 6% extracellular/cell-wall vs
  21% for directly matched ids, p = 0.045).

## Study enrichment: paper, summary, sample tags (2026-10-03)

See `docs/decisions/0007-study-annotations-and-sample-tags.md`.

- [x] `src/aoryzae_atlas/annotation/` (vocabulary, schema/validation, evidence collector, DB ingest),
  migration `0002_study_annotations.sql`, CLI `atlas annotate collect|status|validate|suggest` and
  `atlas database load-annotations`; both run inside `atlas refresh` (collect only for studies with no
  evidence file; network failure = skipped step). `tests/test_annotation.py` (15 tests; 194 pass overall).
- [x] Shared vocabulary `metadata/sample_tag_vocabulary.tsv` (52 tags + parametric families) and curated
  annotations for all 8 studies in `metadata/study_annotations/` -- every study has its originating paper,
  confirmed by NCBI elink or the paper's own deposition statement. Evidence in `reports/study_evidence/`.
- [x] Study side panel: paper title, objective / design / main finding, paper + PubMed links, per-run tag
  chips (toggle to show only tags that differ within the study).
- [x] Curation protocol for new studies: `.claude/skills/annotate-study/SKILL.md`.
- [ ] Apply to `metadata/conditions.tsv` what the papers resolved (PRJDB37930 ctrl/hypo = DO 10% vs <=1%,
  B3h = baseline, AOXA = aoxA deletion; PRJNA121091 ER stress = 20 mM DTT; PRJNA1261861 medium =
  Czapek-Dox + 2% fructose, 28 C) -- needs the user's OK, curated file.
- [ ] Optional: unattended LLM curation step (Claude API) on top of the evidence files + validator.

## Milestones 6-12

- [ ] Not started (see PROJECT_MASTER_SPEC.md section 37 for full list).
  Milestone 7's first slice has a head start -- see the spike above.
  Milestones 9 (gene statistics), 10 (Tsallis/Hill), and 11 (clustering)
  each have a real, tested, standardized CLI command now (`atlas stats
  genes` / `atlas entropy genes` / `atlas cluster genes`, Round 6 above) --
  still not marked complete: no formal validation against those
  milestones' full acceptance criteria has been done, and Milestone 8
  (broader study/condition coverage) hasn't run yet, which the notebook's
  own report flags as a precondition for trusting the classification at
  more than pilot scale.
