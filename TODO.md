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
- [ ] Not yet done: populate `metadata/gene_external_identifiers.tsv` from
      this reconciliation (UniProtKB_accession/UniProtKB_entry_name/
      gene_alias namespaces from the workbook; a FungiDB namespace from
      `GeneAliases.txt`'s AO09/AO07/AspGD triples) -- deferred as a separate
      increment so the audit step above could be reviewed on its own first.
- [ ] Not yet decided: whether `database/FungiDB_v71/` should move under
      `reference/` to match PROJECT_MASTER_SPEC.md section 7's layout
      (`database/` is specified to hold only `atlas.duckdb`). Left as-is
      for now; easy to `git mv` later since payloads are gitignored either
      way.

## Milestone 2 — Public transcriptome discovery report

- [ ] Not started.

## Milestone 3 — Canonical RIB40 reference

- [ ] Not started. `config/reference.yaml` stays unfrozen until this
      milestone is complete.

## Milestones 4-12

- [ ] Not started (see PROJECT_MASTER_SPEC.md section 37 for full list).
