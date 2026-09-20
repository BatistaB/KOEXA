"""AOED command-line interface.

Implements the CLI shell described in PROJECT_MASTER_SPEC.md section 25.
`init`, `doctor`, `status`, `storage status`, and `identifiers reconcile`
(Milestone 1) are functional; every other subcommand exists so the intended
CLI shape is discoverable, but raises a clear "not implemented yet" error
naming the milestone that will implement it. This avoids pretending to
download, process, or classify anything before those milestones' safety and
correctness requirements (data integrity, storage safety, provenance) are
actually built.
"""
from __future__ import annotations

import shutil
import sys
from pathlib import Path

import click

from .. import __version__
from ..config import ConfigError, load_storage_config
from ..doctor import doctor_report_text
from ..identifiers.reconcile import render_summary_report, run_reconciliation, write_mapping_tsv
from ..logging_setup import get_logger
from ..paths import (
    DATABASE_FILE,
    FUNGIDB_PROTEIN_FASTA_FILE,
    GENE_ID_MAPPING_FILE,
    GENE_ID_MAPPING_REPORT_FILE,
    PROJECT_ROOT,
    REQUIRED_CONFIG_FILES,
    REQUIRED_DIRS,
    SCRATCH_DIR,
    UNIPROT_WORKBOOK_FILE,
)
from ..runtime_status import init_runtime_status, load_runtime_status

logger = get_logger("cli")


def _not_implemented(milestone: str, what: str) -> None:
    raise click.ClickException(
        f"'{what}' is not implemented yet. It is scoped to {milestone} in "
        f"PROJECT_MASTER_SPEC.md and must not run ahead of its prerequisites "
        f"(data integrity, storage safety, and provenance requirements)."
    )


@click.group()
@click.version_option(version=__version__, prog_name="atlas")
def cli() -> None:
    """AOED / Aspergillus oryzae Transcriptome Atlas command-line interface."""


@cli.command()
def init() -> None:
    """Create/validate the project directory tree and runtime status file.

    Never overwrites existing configuration or runtime state. Safe to run
    repeatedly (idempotent).
    """
    missing_dirs = [d for d in REQUIRED_DIRS if not d.is_dir()]
    for d in missing_dirs:
        d.mkdir(parents=True, exist_ok=True)
        logger.info("Created missing directory: %s", d)

    missing_configs = [f for f in REQUIRED_CONFIG_FILES if not f.is_file()]
    if missing_configs:
        for f in missing_configs:
            click.echo(f"WARNING: missing config file (not created automatically): {f}", err=True)

    status = init_runtime_status()
    logger.info("Runtime status ready (initialized_at=%s)", status.initialized_at)

    click.echo(f"AOED project root: {PROJECT_ROOT}")
    click.echo(f"Directories created this run: {len(missing_dirs)}")
    if missing_configs:
        click.echo(f"Missing config files: {len(missing_configs)} (see warnings above)")
    else:
        click.echo("All required config files present.")
    click.echo("Runtime status: OK")


@cli.command()
def doctor() -> None:
    """Run environment/sanity checks (required vs. optional)."""
    report, all_required_ok = doctor_report_text()
    click.echo(report)
    if not all_required_ok:
        sys.exit(1)


def _scratch_usage_bytes() -> int:
    total = 0
    if SCRATCH_DIR.is_dir():
        for p in SCRATCH_DIR.rglob("*"):
            if p.is_file():
                try:
                    total += p.stat().st_size
                except OSError:
                    pass
    return total


def _fmt_gb(num_bytes: float) -> str:
    return f"{num_bytes / (1024 ** 3):.2f} GB"


@cli.command()
def status() -> None:
    """Show the section-25 status block. Milestone 0: mostly zeros/N.A.

    Sample-state counts and Nextflow session info become meaningful once the
    database (Milestone 4) and pipeline orchestration (Milestone 5+) exist.
    """
    rstatus = load_runtime_status()
    disk_total, disk_used, disk_free = shutil.disk_usage(PROJECT_ROOT)
    scratch_bytes = _scratch_usage_bytes()

    db_present = DATABASE_FILE.is_file()

    try:
        storage_cfg = load_storage_config()
        scratch_max_gb = storage_cfg.get("storage", {}).get("scratch_max_gb")
    except ConfigError:
        scratch_max_gb = None

    lines = [
        "Samples discovered:   0 (no database yet)" if not db_present else "Samples discovered:   see database",
        "Approved:             0",
        "Queued:               0",
        "Processing:           0",
        "Archived:             0",
        "QC failed:            0",
        "Excluded:             0",
        "",
        f"Disk free:            {_fmt_gb(disk_free)}",
        f"Scratch usage:        {_fmt_gb(scratch_bytes)}"
        + (f" / max {scratch_max_gb} GB" if scratch_max_gb is not None else ""),
        f"Current sample:       {rstatus.current_sample if rstatus else 'N/A (run `atlas init` first)'}",
        f"Next resumable step:  {rstatus.next_resumable_step if rstatus else 'N/A'}",
        f"Nextflow run/session: {rstatus.nextflow_run_name if rstatus else 'N/A'}",
        f"AOED app:             not implemented yet (Milestone 7)",
    ]
    click.echo("\n".join(lines))


@cli.group()
def identifiers() -> None:
    """AO09/UniProt identifier reconciliation commands (Milestone 1)."""


@identifiers.command("reconcile")
@click.option(
    "--workbook",
    "workbook_path",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    default=UNIPROT_WORKBOOK_FILE,
    show_default=True,
    help="UniProt-derived workbook (.xlsx) supplied as Milestone 1 input evidence.",
)
@click.option(
    "--protein-fasta",
    "protein_fasta_path",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    default=FUNGIDB_PROTEIN_FASTA_FILE,
    show_default=True,
    help="FungiDB RIB40 annotated-protein FASTA supplied as Milestone 1 input evidence.",
)
@click.option(
    "--reference-version",
    default="FungiDB_v71",
    show_default=True,
    help="Label for this evidence snapshot. Not a frozen reference (Milestone 3 freezes one).",
)
def identifiers_reconcile(workbook_path: Path, protein_fasta_path: Path, reference_version: str) -> None:
    """Reconcile the UniProt workbook's AO09 ids against the FungiDB protein FASTA.

    Writes metadata/gene_id_mapping.tsv (the audit trail: one row per
    UniProt-entry/AO09-id link, classified exact/one_to_many/many_to_one/
    ambiguous/unmapped) and a human-readable structural validation report.
    Neither input file is treated as the canonical reference
    (PROJECT_MASTER_SPEC.md section 12); that is Milestone 3's job.
    """
    result = run_reconciliation(workbook_path, protein_fasta_path, reference_version)

    write_mapping_tsv(result.mapping_rows, GENE_ID_MAPPING_FILE)
    logger.info(
        "Wrote %d gene_id_mapping.tsv rows to %s (reference_version=%s)",
        len(result.mapping_rows),
        GENE_ID_MAPPING_FILE,
        reference_version,
    )

    report_text = render_summary_report(result.summary, reference_version)
    GENE_ID_MAPPING_REPORT_FILE.write_text(report_text, encoding="utf-8")
    logger.info("Wrote reconciliation report to %s", GENE_ID_MAPPING_REPORT_FILE)

    click.echo(report_text)
    click.echo(f"Full mapping table: {GENE_ID_MAPPING_FILE}")
    click.echo(f"Full report:        {GENE_ID_MAPPING_REPORT_FILE}")


# --- Stub command groups mirroring PROJECT_MASTER_SPEC.md section 25 -------

@cli.group()
def dataset() -> None:
    """Dataset discovery/curation commands (Milestone 2)."""


@dataset.command("add")
@click.argument("accession")
def dataset_add(accession: str) -> None:
    _not_implemented("Milestone 2 (Public transcriptome discovery report)", f"atlas dataset add {accession}")


@dataset.command("discover")
def dataset_discover() -> None:
    _not_implemented("Milestone 2 (Public transcriptome discovery report)", "atlas dataset discover")


@dataset.command("list")
def dataset_list() -> None:
    _not_implemented("Milestone 2 (Public transcriptome discovery report)", "atlas dataset list")


@cli.group()
def discovery() -> None:
    """Discovery reporting commands (Milestone 2)."""


@discovery.command("report")
def discovery_report() -> None:
    _not_implemented("Milestone 2 (Public transcriptome discovery report)", "atlas discovery report")


@discovery.command("export")
def discovery_export() -> None:
    _not_implemented("Milestone 2 (Public transcriptome discovery report)", "atlas discovery export")


@cli.group()
def sample() -> None:
    """Per-sample approval/queueing commands (Milestone 4+)."""


@sample.command("approve")
@click.argument("srr")
def sample_approve(srr: str) -> None:
    _not_implemented("Milestone 4 (Database, state, and storage safety)", f"atlas sample approve {srr}")


@sample.command("queue")
@click.argument("srr")
def sample_queue(srr: str) -> None:
    _not_implemented("Milestone 4 (Database, state, and storage safety)", f"atlas sample queue {srr}")


@cli.command()
def fetch() -> None:
    """Fetch approved samples via nf-core/fetchngs (Milestone 5)."""
    _not_implemented("Milestone 5 (One sample end-to-end)", "atlas fetch approved")


@cli.group()
def process() -> None:
    """Processing commands (Milestone 5+)."""


@process.command("next")
def process_next() -> None:
    _not_implemented("Milestone 5 (One sample end-to-end)", "atlas process next")


@process.command("batch")
@click.option("--n", default=1, show_default=True, help="Batch size.")
def process_batch(n: int) -> None:
    _not_implemented("Milestone 5 (One sample end-to-end)", f"atlas process batch --n {n}")


@cli.command()
def pause() -> None:
    """Request a graceful pause at the next safe task boundary (Milestone 4)."""
    _not_implemented("Milestone 4 (Database, state, and storage safety)", "atlas pause")


@cli.command()
def resume() -> None:
    """Resume unfinished work without reprocessing completed samples (Milestone 4)."""
    _not_implemented("Milestone 4 (Database, state, and storage safety)", "atlas resume")


@cli.group()
def storage() -> None:
    """Storage Guardian commands (spec section 5)."""


@storage.command("status")
def storage_status() -> None:
    disk_total, disk_used, disk_free = shutil.disk_usage(PROJECT_ROOT)
    scratch_bytes = _scratch_usage_bytes()
    try:
        cfg = load_storage_config()["storage"]
    except (ConfigError, KeyError):
        cfg = {}
    click.echo(f"Disk free:          {_fmt_gb(disk_free)} (minimum required: {cfg.get('minimum_free_gb', '?')} GB)")
    click.echo(f"Scratch usage:      {_fmt_gb(scratch_bytes)} (max: {cfg.get('scratch_max_gb', '?')} GB)")
    click.echo(f"Max parallel samples: {cfg.get('max_parallel_samples', '?')}")


@storage.command("clean")
def storage_clean() -> None:
    _not_implemented(
        "Milestone 4/5 (Storage Guardian deletion rules, spec section 5)",
        "atlas storage clean",
    )


@cli.group()
def qc() -> None:
    """QC commands (Milestone 5+)."""


@qc.command("sample")
@click.argument("srr")
def qc_sample(srr: str) -> None:
    _not_implemented("Milestone 5 (One sample end-to-end)", f"atlas qc sample {srr}")


@qc.command("replicates")
def qc_replicates() -> None:
    _not_implemented("Milestone 6 (One replicated condition)", "atlas qc replicates")


@cli.group()
def matrix() -> None:
    """Matrix-building commands (Milestone 5+)."""


@matrix.command("build")
def matrix_build() -> None:
    _not_implemented("Milestone 5/6 (sample-level and condition-level TPM matrices)", "atlas matrix build")


@cli.group(name="app")
def app_group() -> None:
    """AOED interactive application commands (Milestone 7)."""


@app_group.command("serve")
def app_serve() -> None:
    _not_implemented("Milestone 7 (AOED basic interface)", "atlas app serve")


@cli.group()
def stats() -> None:
    """Gene-level statistics commands (Milestone 9)."""


@stats.command("genes")
def stats_genes() -> None:
    _not_implemented("Milestone 9 (Gene statistics)", "atlas stats genes")


@cli.group()
def entropy() -> None:
    """Tsallis/Hill diversity commands (Milestone 10)."""


@entropy.command("genes")
def entropy_genes() -> None:
    _not_implemented("Milestone 10 (Tsallis/Hill)", "atlas entropy genes")


@cli.group()
def cluster() -> None:
    """Clustering commands (Milestone 11)."""


@cluster.command("genes")
def cluster_genes() -> None:
    _not_implemented("Milestone 11 (Clustering and biological interpretation)", "atlas cluster genes")


@cli.group()
def report() -> None:
    """Report-generation commands."""


@report.command("build")
def report_build() -> None:
    _not_implemented("Milestone 12 (Advanced AOED report)", "atlas report build")


if __name__ == "__main__":
    cli()
