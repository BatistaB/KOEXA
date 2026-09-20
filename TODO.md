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

- [ ] Awaiting new source files: the previously supplied UniProt-derived
      workbook and RIB40 protein FASTA were removed from the project folder
      by the user. Milestone 1 is blocked until equivalent verified sources
      are provided or re-acquired from an authoritative source (UniProt /
      NCBI / FungiDB), with checksums.

## Milestone 2 — Public transcriptome discovery report

- [ ] Not started.

## Milestone 3 — Canonical RIB40 reference

- [ ] Not started. `config/reference.yaml` stays unfrozen until this
      milestone is complete.

## Milestones 4-12

- [ ] Not started (see PROJECT_MASTER_SPEC.md section 37 for full list).
