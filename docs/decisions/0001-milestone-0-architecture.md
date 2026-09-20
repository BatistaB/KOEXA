# ADR 0001: Milestone 0 repository architecture

Date: 2026-09-20
Status: Accepted

## Context

PROJECT_MASTER_SPEC.md section 40 asks for the exact AOED repository
architecture and local launcher to be proposed before writing code, and
section 37 (Milestone 0) asks for a runnable shell: structure, config,
logging, CLI, tests, and an audit of AFED, without downloading any data.

The user confirmed (2026-09-20):
- The connected folder `D:\PanTranscriptome` itself is the repository root
  (no extra `aoryzae-transcriptome-atlas/` wrapper folder).
- Scaffolding work happens directly on the user's machine through the
  device bridge, not built elsewhere and copied over.
- The two files that had been supplied as Milestone 1 evidence
  (`Archive_3_AoryzaeRIB40_Proteins.fasta`, `Archive_9_PSIM_Aory.xlsx`) were
  deleted by the user before this work started. Milestone 1 (AO09/UniProt
  reconciliation) is therefore blocked until equivalent verified sources are
  supplied again or re-acquired from an authoritative source with checksums.
  This is tracked in `TODO.md`.

## Decisions

1. **Directory layout**: follow PROJECT_MASTER_SPEC.md section 7 exactly,
   rooted at the repository root instead of a nested project folder.
   `PROJECT_MASTER_SPEC_Aoryzae_Transcriptome_Atlas.md` was renamed to
   `PROJECT_MASTER_SPEC.md` to match the structure the spec itself defines
   (a rename, not a deletion — the content is untouched).

2. **Language/runtime**: Python 3.10+ for the CLI and all AOED-specific
   logic (identifier reconciliation, condition curation, database ingestion,
   storage policy, atlas construction, analytics). This matches the
   `notebooks/` layout already specified (Jupyter) and keeps one language
   for everything except the eventual Shiny app layer (Milestone 7, see ADR
   0002) and the PowerShell launcher.

3. **CLI framework**: `click`. Already present in the base environment,
   widely used, supports command groups matching the section-25 command
   tree (`atlas dataset ...`, `atlas sample ...`, etc.) with minimal
   boilerplate, and integrates with `click.testing.CliRunner` for tests
   without extra dependencies.

4. **Database**: DuckDB, as the spec defaults to unless testing finds a
   reason otherwise (section 8). Not yet exercised in this environment
   (see "Known gaps" below) — the schema/ingestion code itself is deferred
   to Milestone 4, so this milestone only pins the dependency in
   `pyproject.toml`.

5. **Config format**: plain YAML files under `config/`, loaded as plain
   dicts (`aoryzae_atlas.config`). No schema-validation library added yet to
   keep Milestone 0 dependencies minimal; `ConfigError` is raised on missing
   or malformed files rather than silently defaulting. `reference.yaml`
   ships with every scientifically meaningful field set to `null` and
   `frozen: false` — per section 3.1, nothing here is allowed to be
   invented, and the pipeline is expected to check `is_reference_frozen()`
   before large-scale quantification once that code exists.

6. **Logging**: Python's stdlib `logging`, console + rotating file handler
   under `results/logs/atlas.log`. Deliberately simple; revisit only if a
   real need for structured/JSON logging emerges once pipeline orchestration
   (Nextflow) is wired in.

7. **Runtime status**: a small `runtime/status.json`, written atomically
   (temp file + `os.replace`) via `aoryzae_atlas.runtime_status`. This is a
   stand-in for the richer state described in section 6 (which lives in
   DuckDB once Milestone 4 exists) — it exists now only so `atlas status`
   and `atlas init` have something concrete and resumable to show/manage.

8. **CLI completeness vs. honesty**: every command named in spec section 25
   exists in the CLI (`atlas dataset discover`, `atlas process next`, etc.),
   but only `init`, `doctor`, `status`, and `storage status` do real work.
   Every other command raises a `click.ClickException` naming the milestone
   responsible for implementing it. This was chosen over omitting the
   commands entirely so `atlas --help` reflects the intended final shape,
   and over silently no-op'ing them so nobody mistakes a stub for a working
   pipeline step.

9. **Windows launcher**: `run_atlas.ps1` creates `.venv` on first run,
   installs the package in editable mode (re-installing only when
   `pyproject.toml`'s hash changes), and forwards arguments to
   `python -m aoryzae_atlas.cli.main`. Defaults to `status` when called with
   no arguments. Nextflow itself is not invoked yet (Milestone 5+).

## Known gaps / explicit non-goals for Milestone 0

- The scaffolding and tests above were written and exercised through the
  Cowork device bridge's own Linux environment, which has no outbound
  network access. `duckdb`, `pytest`, and `rich` are pinned in
  `pyproject.toml` but could not actually be `pip install`-ed or imported
  there. All test logic was additionally hand-verified by direct function
  calls (see commit history / session log) to confirm correctness, but
  **running the real `pytest` suite on the user's own Windows Python
  environment (via `run_atlas.ps1`, which does have network access) is an
  outstanding verification step**, tracked in `TODO.md`.
- No container/Conda strategy has been chosen yet for Nextflow/nf-core
  execution (WSL2 + Docker Desktop vs. Conda/Mamba, per spec section 29).
  `config/pipeline.yaml` leaves `execution.profile` and
  `execution.container_engine` as `null` until that decision is made,
  which should happen before Milestone 5.
- No RIB40 reference accessions were looked up or entered anywhere. That is
  explicitly Milestone 3's job, and inventing them here would violate
  section 3.1.
