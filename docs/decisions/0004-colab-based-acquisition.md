# ADR 0004: Move FASTQ acquisition + QC + quantification to Google Colab

Date: 2026-09-21
Status: Accepted (supersedes ADR 0003 for the acquisition/quantification step only)

## Context

ADR 0003 committed to running `nf-core/fetchngs` and `nf-core/rnaseq` locally
via Nextflow inside a WSL2 Ubuntu distro, using Docker Desktop as the
container engine. That worked end-to-end for the first sample (DRR786485,
Milestone 5) once the unrelated C:-drive-full bug was fixed (see TODO.md).

Attempting a second batch (PRJDB4747: DRR059464/65/66) surfaced a *different*
problem: this machine's home internet connection downloads from the ENA FTP
mirror at roughly 2MB/min, regardless of Nextflow/Docker/WSL2 configuration
(confirmed not a bug in our stack -- `wget` of the exact same URL, run
directly, is equally slow here). A side-by-side test downloading the same
three files from a Google Colab notebook (2026-09-21) measured 16.2s, 102.4s,
and 170.4s respectively -- Colab's network egress is dramatically faster for
this workload than this machine's home connection.

Given that, doing acquisition + quantification locally is actively
counterproductive: every sample would spend the vast majority of its
wall-clock time blocked on this machine's slow downlink, for no benefit,
when the exact same work finishes in a small fraction of the time on
infrastructure already available for free.

## Decision

FASTQ acquisition, QC, trimming, and quantification now happen in a Google
Colab notebook (`workflows/colab_pantranscriptome.ipynb`), not on this
machine. Only post-processing -- ingesting the Colab-produced results into
`database/atlas.duckdb` and everything downstream (matrices, stats, the app)
-- remains local.

The Colab notebook does **not** reuse `nf-core/fetchngs`/`nf-core/rnaseq` via
Nextflow, because Colab has no Docker support (no privileged/container-in-
container access) and standing up Nextflow + conda-per-process there adds
real setup fragility for no benefit given Colab's ephemeral, frequently-reset
runtime. Instead it calls the same underlying tools directly:

- `wget` against ENA's FTP mirror (same URLs/retry flags `nf-core/fetchngs`
  itself uses; resolved via the same ENA Portal filereport API, with MD5
  verification) instead of the `SRA_FASTQ_FTP` module.
- `fastqc` + `fastp` for QC/trimming instead of
  `FASTQ_FASTQC_UMITOOLS_TRIMGALORE`.
- `salmon quant` against a decoy-aware index (genome + transcript FASTA,
  same recipe `nf-core/rnaseq` uses) instead of
  `QUANTIFY_PSEUDO_ALIGNMENT`/`SALMON_QUANT`.
- A small pandas step aggregates `quant.sf` to gene level via the existing
  `reference/transcripts/t2g.tsv`, replacing tximport.

This intentionally drops the parts of `nf-core/rnaseq` this project wasn't
using anyway (STAR alignment, BAM-based QC, StringTie, MultiQC aggregation)
and keeps the ones it was: Salmon transcript quantification with a
decoy-aware index (`reference.yaml`'s frozen RIB40_v1), FastQC, and
adapter/quality trimming. Salmon was kept as the quantifier (not switched to
Kallisto) specifically to stay consistent with PROJECT_MASTER_SPEC.md section
9 ("prefer Salmon transcript-level quantification") and with DRR786485's
already-quantified results.

Per-sample flow in the notebook (implemented as a recursive driver over a
fixed accession list, so it can be interrupted and re-run safely):
download (1h timeout) -> FastQC -> fastp -> FastQC -> Salmon quant -> gene
aggregation -> copy only the analysis outputs (FastQC reports, `quant.sf`,
gene-level TSV) to Google Drive under `MyDrive/PanTranscriptome/results/` and
mark a `DONE` file. Raw and trimmed FASTQ are always deleted from Colab's
local disk before moving to the next sample -- they never reach Drive. A
sample whose folder exists without a `DONE` marker (interrupted mid-run) is
deleted and reprocessed from scratch on the next invocation, rather than
attempting fine-grained mid-task resume.

## Consequences

- `workflows/process_samples.sh`, `workflows/mark_sample_status.py`, and
  `config/nextflow_resource_limits.config` (the WSL2/Nextflow batch driver
  and its DB-status-tracking helper, built 2026-09-21 immediately before this
  pivot) are removed: superseded before ever being used for a real batch.
  Their content is preserved in git history if the local-Nextflow approach
  needs revisiting.
- `database/atlas.duckdb`'s `pipeline_status`/`qc_status`/`quant_status`
  tracking is no longer updated automatically by anything running on this
  machine during acquisition -- the Colab notebook tracks its own progress
  independently (`MyDrive/PanTranscriptome/logs/progress.csv` + per-sample
  `DONE` markers on Drive), and ingesting a finished sample's results back
  into the DB (not yet implemented) is where `pipeline_status` should be
  updated going forward.
- This machine's role in Milestone 5 onward is: approve samples
  (`atlas sample approve`), add them to the notebook's `ACCESSIONS` list,
  wait for Colab, then pull `MyDrive/PanTranscriptome/results/<acc>/` back
  and ingest it -- not run Nextflow/Docker at all for new samples.
- WSL2 + Docker Desktop (ADR 0003) are **not** being removed from this
  machine -- they may still be useful for local experimentation -- but are
  no longer in the critical path for growing the atlas.

## Known issue: bioconda salmon build vs. Colab's assigned CPU, and vs. condacolab's python=3.13 pin

Two separate, stacked problems hit while getting Salmon running in Colab
(2026-09-21):

1. `salmon=1.10.3` (this ADR's original pin) crashes with SIGSEGV on some
   Colab CPU allocations -- confirmed even `salmon --version` alone, with no
   input files touched, dies with SIGSEGV. Classic signature of a bioconda
   build using an AVX2/AVX-512 instruction the assigned VM's CPU doesn't
   support, not a bug in our FASTA/decoy inputs or command.
2. Downgrading to `salmon=1.10.1` (which doesn't hit the SIGSEGV -- its
   binary printed its version fine) turned out to be **structurally
   impossible to install into condacolab's base environment**: condacolab
   hard-pins `python=3.13`, every `python=3.13.x` build requires
   `libzlib >=1.3.x`, and `salmon=1.10.1`'s build requires
   `libzlib <1.3.0a0`. There is no valid combination. The first attempt to
   force it anyway (`mamba install salmon=1.10.1` on an environment that
   already had `pandas` pulling in the newer zlib) didn't fail cleanly --
   mamba "solved" it by unlinking 41 packages including `conda`, `mamba`,
   and `python-3.13.13` itself, leaving the environment broken (a fresh,
   from-scratch attempt correctly reported "Could not solve for environment
   specs" instead, with no destructive side effect -- the unsafe outcome
   only happened once the base env had already drifted from repeated
   installs).

Fix: never install Salmon into condacolab's base environment. Create a
separate named conda env (`transcriptome`, `python=3.11`, no python-version
pin) and install `salmon=1.10.1` there instead -- python 3.11 has no
zlib-version conflict with it. `fastqc`/`fastp`/`pandas`/`requests` go in
the same env. The notebook prepends
`/usr/local/envs/transcriptome/bin` to `PATH` after creating it so every
later `subprocess.run([...])` call finds the env's tools transparently,
without needing `conda activate` machinery inside a non-interactive kernel.
Credit: this env-isolation approach is the user's own previously-working
recipe from an earlier unrelated project, adapted here.

Since Colab doesn't guarantee the same CPU model across sessions, the
SIGSEGV could still recur on a future session even with `salmon=1.10.1`; if
so, retry inside the `transcriptome` env with `1.10.0`'s precompiled binary
(`https://github.com/COMBINE-lab/salmon/releases/download/v1.10.0/salmon-1.10.0_linux_x86_64.tar.gz`,
confirmed to exist -- unlike `1.10.1`, which has no precompiled binary
asset, source-only) rather than fighting the conda solver further.

## Alternatives considered and rejected

- **Fix Nextflow's Aspera download method for higher throughput on this
  machine**: tried first (2026-09-21); `nf-core/fetchngs`'s bundled
  `aspera-cli:4.14.0` container failed with `ascp: failed to authenticate`
  (its bundled bypass key is rejected by ENA's current endpoint) regardless
  of network conditions. Not pursued further -- fixing a bundled biocontainer
  key is more effort than the problem (this machine's own downlink) is worth
  solving locally at all.
- **Raise WSL2's memory/resource ceiling or otherwise tune the local
  network stack**: irrelevant -- the bottleneck is confirmed to be this
  machine's ISP/local network path to ENA, not WSL2, Docker, or Nextflow
  configuration.
- **Keep Nextflow but run it inside Colab via `-profile conda`**: would
  have preserved `nf-core/fetchngs`/`nf-core/rnaseq` as-is, but installing
  conda (via `condacolab`, which itself requires a runtime restart) plus
  per-process environment creation adds meaningful, repeated setup cost on
  Colab's frequently-reset ephemeral runtime, for a pipeline whose full
  feature set (STAR, BAM QC, StringTie, MultiQC) wasn't being used anyway.
  Direct tool calls (this decision) are lighter and faster to iterate on in
  a notebook someone is actively watching and pausing/resuming by hand.
