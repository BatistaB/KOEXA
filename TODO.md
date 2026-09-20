# TODO — AOED / Aspergillus oryzae Transcriptome Atlas

Tracks live progress against the milestones in `PROJECT_MASTER_SPEC.md`
section 37. Keep this file honest: check an item only when it is actually
done, not scaffolded.

## Milestone 0 — Repository and runnable AOED shell

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
- [ ] Decide and record the container/execution strategy (Docker Desktop +
      WSL2 vs. Conda) for Nextflow/nf-core on the user's machine.
- [ ] Set up a real Python environment on the user's Windows machine and
      confirm `run_atlas.ps1 doctor` passes there (this was only exercised
      in the Linux file-bridge environment so far).

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
