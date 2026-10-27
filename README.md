# KOEXA — KOji EXpression Atlas

A reproducible, public RNA-seq compendium and transcriptome atlas for
*Aspergillus oryzae*, inspired by [AFED](https://github.com/kcamnairb/a_flavus_expression_db)
(*Aspergillus flavus* Expression Database; MIT-licensed; Mack & Lebar,
*Database*, 2025, [baaf033](https://doi.org/10.1093/database/baaf033)).

The full specification lives in [`PROJECT_MASTER_SPEC.md`](PROJECT_MASTER_SPEC.md)
and is the source of truth for scope, priorities, and milestones. This
README is an orientation pointer only — when in doubt, the spec wins.

## Status

Milestones 0-3 are complete:

- **Milestone 0** (repository and runnable KOEXA shell): CLI shell
  (`atlas doctor` / `atlas init` / `atlas status`) functional on the
  maintainer's Windows machine; Nextflow/nf-core execution available via
  Docker Desktop (WSL2 backend) with a WSL2 Ubuntu distro running Nextflow
  — see `docs/decisions/0003-execution-strategy.md`.
- **Milestone 1** (AO09/UniProt reconciliation): `atlas identifiers
  reconcile` and `atlas genes build-master` populate
  `metadata/gene_id_mapping.tsv`, `gene_external_identifiers.tsv`, and
  `gene_master.tsv` against the FungiDB v71 evidence set.
- **Milestone 2** (public transcriptome discovery): `atlas discovery
  report` queries NCBI SRA and writes `reports/discovery/`; 458
  *A. oryzae* RNA-Seq runs found so far. Discovery only — no FASTQ/SRA data
  downloaded, no sample approved for processing yet.
- **Milestone 3** (canonical RIB40 reference): `atlas reference validate`
  verified the evidence set against NCBI's Assembly database and
  `config/reference.yaml` is now **frozen** (`reference_version:
  RIB40_v1`, assembly `GCF_000184455.2`).

There is still no downloaded RNA-seq data and no expression matrix. Every
subcommand beyond what's listed above is an intentional stub that names the
milestone that will implement it (see `atlas --help` and
`src/aoryzae_atlas/cli/main.py`).

See [`TODO.md`](TODO.md) for the live milestone checklist and
[`docs/decisions/`](docs/decisions/) for recorded design decisions,
including the AFED audit.

## Quick start (Windows)

```powershell
.\run_atlas.ps1 doctor
.\run_atlas.ps1 init
.\run_atlas.ps1 status
```

`run_atlas.ps1` creates a local `.venv` on first run and installs this
package in editable mode — no manual venv activation or Nextflow commands
required.

## Quick start (any OS, manual)

```bash
python3 -m venv .venv
source .venv/bin/activate        # .venv\Scripts\Activate.ps1 on Windows
pip install -e ".[dev]"
atlas doctor
atlas init
atlas status
```

## Design priorities

In order (PROJECT_MASTER_SPEC.md section 0): data integrity, reproducibility,
safe storage management, traceability/provenance, resumability after
interruption, quality control, correct biological metadata, extensibility,
performance. Nothing in this codebase should trade a higher priority for a
lower one without an explicit, documented decision (see `docs/decisions/`).

## Repository layout

See PROJECT_MASTER_SPEC.md section 7 for the authoritative layout and the
rationale behind each directory. In short: `config/` holds pinned,
human-edited YAML (never invented accession numbers); `metadata/` holds
schema-only TSVs until real samples are curated; `src/aoryzae_atlas/` is the
Python package; `scratch/` and raw FASTQ/SRA are never committed and never
kept permanently on disk (see the Storage Guardian, section 5).

## License and attribution

KOEXA-specific code is original. Any component substantially derived from
AFED (MIT-licensed) retains its license and copyright notice and is called
out explicitly in code comments and in `docs/decisions/`.
