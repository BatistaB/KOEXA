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

import hashlib
import shutil
import sys
from dataclasses import replace
from datetime import date, datetime, timezone
from pathlib import Path

import click
import duckdb

from .. import __version__
from ..config import ConfigError, load_pipeline_config, load_reference_config, load_storage_config
from ..database.approve import SampleExcludedError, SampleNotFoundError, approve_sample
from ..database.ingest_discovery import load_datasets, load_samples
from ..database.ingest_genes import load_gene_external_identifiers, load_genes
from ..database.ingest_results import (
    ResultsIncompleteError,
    ResultsNotFoundError,
    find_ingestable_accessions,
    ingest_sample_results,
)
from ..database.migrate import apply_migrations
from ..database.queries import sample_status_counts
from ..discovery import sra_search
from ..discovery.classify import build_discovery_tables
from ..discovery.crossref import apply_crossrefs_to_studies, fetch_study_crossrefs
from ..discovery.parse import load_discovered_runs
from ..discovery.report import render_markdown_report, write_discovery_tsvs
from ..doctor import doctor_report_text
from ..identifiers.external_identifiers import (
    from_gene_aliases_file,
    from_uniprot_mapping,
    write_external_identifiers_tsv,
)
from ..identifiers.reconcile import render_summary_report, run_reconciliation, write_mapping_tsv
from ..logging_setup import get_logger
from ..metadata.gene_master import build_gene_master_rows, write_gene_master_tsv
from ..metadata.gene_product_updates import load_b71_products
from ..metadata.gff import load_protein_coding_genes
from ..state import SampleState
from ..paths import (
    DATABASE_FILE,
    DISCOVERY_DIR,
    DISCOVERY_RAW_API_RESPONSES_DIR,
    FUNGIDB_GENE_ALIASES_FILE,
    FUNGIDB_GENE_PRODUCT_UPDATES_FILE,
    FUNGIDB_GENOME_FASTA_FILE,
    FUNGIDB_GFF_FILE,
    FUNGIDB_PROTEIN_FASTA_FILE,
    FUNGIDB_TRANSCRIPT_FASTA_FILE,
    GENE_EXTERNAL_IDENTIFIERS_FILE,
    GENE_ID_MAPPING_FILE,
    GENE_ID_MAPPING_REPORT_FILE,
    GENE_MASTER_FILE,
    PROJECT_ROOT,
    REFERENCE_VALIDATION_REPORT_FILE,
    REQUIRED_CONFIG_FILES,
    REQUIRED_DIRS,
    RESULTS_DIR,
    SCRATCH_DIR,
    TRANSCRIPT_TO_GENE_FILE,
    UNIPROT_WORKBOOK_FILE,
)
from ..reference.transcript_to_gene import load_transcript_to_gene, write_t2g_tsv
from ..reference.validate import render_validation_report, validate_reference
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
    """Show the section-25 status block.

    Sample-state counts come from the database once it exists (Milestone 4);
    Nextflow session info becomes meaningful once pipeline orchestration
    (Milestone 5+) exists.
    """
    rstatus = load_runtime_status()
    disk_total, disk_used, disk_free = shutil.disk_usage(PROJECT_ROOT)
    scratch_bytes = _scratch_usage_bytes()

    counts = sample_status_counts(DATABASE_FILE)

    try:
        storage_cfg = load_storage_config()
        scratch_max_gb = storage_cfg.get("storage", {}).get("scratch_max_gb")
    except ConfigError:
        scratch_max_gb = None

    lines = [
        f"Samples discovered:   {counts['discovered']}" if counts else "Samples discovered:   0 (no database yet)",
        f"Approved:             {counts.get('approved', 0)}",
        f"Queued:               {counts.get('queued', 0)}",
        f"Processing:           {counts.get('processing', 0)}",
        f"Archived:             {counts.get('archived', 0)}",
        f"QC failed:            {counts.get('qc_failed', 0)}",
        f"Excluded:             {counts.get('excluded', 0)}",
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


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


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
    "--gene-aliases",
    "gene_aliases_path",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    default=FUNGIDB_GENE_ALIASES_FILE,
    show_default=True,
    help="FungiDB GeneAliases.txt (AO09/AO07/AspGD triples) for the FungiDB external-identifier namespace.",
)
@click.option(
    "--reference-version",
    default="FungiDB_v71",
    show_default=True,
    help="Label for this evidence snapshot. Not a frozen reference (Milestone 3 freezes one).",
)
def identifiers_reconcile(
    workbook_path: Path,
    protein_fasta_path: Path,
    gene_aliases_path: Path,
    reference_version: str,
) -> None:
    """Reconcile the UniProt workbook's AO09 ids against the FungiDB protein FASTA.

    Writes metadata/gene_id_mapping.tsv (the audit trail: one row per
    UniProt-entry/AO09-id link, classified exact/one_to_many/many_to_one/
    ambiguous/unmapped), metadata/gene_external_identifiers.tsv (the curated
    cross-reference table, scoped to AO09 ids confirmed present in the
    FungiDB v71 gene set), and a human-readable structural validation
    report. Neither input file is treated as the canonical reference
    (PROJECT_MASTER_SPEC.md section 12); that is Milestone 3's job.
    """
    result = run_reconciliation(workbook_path, protein_fasta_path, reference_version, gene_aliases_path=gene_aliases_path)

    write_mapping_tsv(result.mapping_rows, GENE_ID_MAPPING_FILE)
    logger.info(
        "Wrote %d gene_id_mapping.tsv rows to %s (reference_version=%s)",
        len(result.mapping_rows),
        GENE_ID_MAPPING_FILE,
        reference_version,
    )

    external_rows = from_uniprot_mapping(
        result.mapping_rows,
        result.uniprot_rows,
        source_file=workbook_path.name,
        source_checksum=_sha256_file(workbook_path),
    )
    external_rows += from_gene_aliases_file(
        gene_aliases_path,
        result.fungidb_gene_ids,
        reference_version,
        source_file=gene_aliases_path.name,
        source_checksum=_sha256_file(gene_aliases_path),
    )
    write_external_identifiers_tsv(external_rows, GENE_EXTERNAL_IDENTIFIERS_FILE)
    logger.info(
        "Wrote %d gene_external_identifiers.tsv rows to %s",
        len(external_rows),
        GENE_EXTERNAL_IDENTIFIERS_FILE,
    )

    report_text = render_summary_report(result.summary, reference_version)
    GENE_ID_MAPPING_REPORT_FILE.write_text(report_text, encoding="utf-8")
    logger.info("Wrote reconciliation report to %s", GENE_ID_MAPPING_REPORT_FILE)

    click.echo(report_text)
    click.echo(f"Full mapping table:        {GENE_ID_MAPPING_FILE}")
    click.echo(f"External identifiers:      {GENE_EXTERNAL_IDENTIFIERS_FILE} ({len(external_rows)} rows)")
    click.echo(f"Full report:               {GENE_ID_MAPPING_REPORT_FILE}")


@cli.group()
def genes() -> None:
    """Gene master-table commands (Milestone 1, spec section 12)."""


@genes.command("build-master")
@click.option(
    "--gff",
    "gff_path",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    default=FUNGIDB_GFF_FILE,
    show_default=True,
    help="FungiDB RIB40 annotation GFF3 supplied as Milestone 1 input evidence.",
)
@click.option(
    "--gene-product-updates",
    "updates_path",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    default=FUNGIDB_GENE_PRODUCT_UPDATES_FILE,
    show_default=True,
    help="FungiDB gene_product_updates_b71.txt (overrides GFF descriptions where present).",
)
@click.option(
    "--reference-version",
    default="FungiDB_v71",
    show_default=True,
    help="Label for this evidence snapshot. Not a frozen reference (Milestone 3 freezes one).",
)
def genes_build_master(gff_path: Path, updates_path: Path, reference_version: str) -> None:
    """Build metadata/gene_master.tsv from the FungiDB v71 GFF3 + product updates.

    gene_symbol/gene_name are left blank (see metadata.gene_master module
    docstring: the only symbol evidence is ambiguous multi-alias UniProt
    data, already recorded without picking a winner in
    gene_external_identifiers.tsv). Not the canonical/frozen reference
    (Milestone 3's job).
    """
    genes_found = load_protein_coding_genes(gff_path)
    b71_products = load_b71_products(updates_path)
    rows = build_gene_master_rows(genes_found, b71_products, reference_version)
    write_gene_master_tsv(rows, GENE_MASTER_FILE)
    logger.info(
        "Wrote %d gene_master.tsv rows to %s (reference_version=%s)",
        len(rows),
        GENE_MASTER_FILE,
        reference_version,
    )
    click.echo(f"Wrote {len(rows)} gene_master.tsv rows to {GENE_MASTER_FILE}")


@cli.group()
def reference() -> None:
    """Canonical RIB40 reference commands (Milestone 3)."""


@reference.command("validate")
@click.option(
    "--genome",
    "genome_fasta_path",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    default=FUNGIDB_GENOME_FASTA_FILE,
    show_default=True,
    help="RIB40 genome FASTA supplied as Milestone 3 input evidence.",
)
@click.option(
    "--gff",
    "gff_path",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    default=FUNGIDB_GFF_FILE,
    show_default=True,
    help="FungiDB RIB40 annotation GFF3.",
)
@click.option(
    "--protein-fasta",
    "protein_fasta_path",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    default=FUNGIDB_PROTEIN_FASTA_FILE,
    show_default=True,
)
@click.option(
    "--transcript-fasta",
    "transcript_fasta_path",
    type=click.Path(exists=True, dir_okay=False, path_type=Path),
    default=FUNGIDB_TRANSCRIPT_FASTA_FILE,
    show_default=True,
)
def reference_validate(
    genome_fasta_path: Path,
    gff_path: Path,
    protein_fasta_path: Path,
    transcript_fasta_path: Path,
) -> None:
    """Structurally validate the Milestone 3 reference evidence.

    Cross-checks the genome/annotation/transcript files against each other
    and against Milestone 1's protein FASTA gene set, computes checksums,
    and writes the transcript-to-gene mapping. Does NOT flip
    config/reference.yaml's `frozen` flag -- PROJECT_MASTER_SPEC.md section
    37 says to "stop and report if AO09/reference assumptions remain
    unclear", so freezing needs an explicit human sign-off after reviewing
    this report, not an automatic step here. Does not build a Salmon index
    either (Milestone 5, via nf-core/rnaseq).
    """
    report = validate_reference(genome_fasta_path, gff_path, protein_fasta_path, transcript_fasta_path)
    report_text = render_validation_report(report)

    t2g_pairs = load_transcript_to_gene(transcript_fasta_path)
    TRANSCRIPT_TO_GENE_FILE.parent.mkdir(parents=True, exist_ok=True)
    write_t2g_tsv(t2g_pairs, TRANSCRIPT_TO_GENE_FILE)

    REFERENCE_VALIDATION_REPORT_FILE.write_text(report_text, encoding="utf-8")
    logger.info(
        "Reference validation: %d genome sequences, %d GFF genes, %d problems -> %s",
        report.genome_sequence_count,
        report.gff_gene_count,
        len(report.problems),
        REFERENCE_VALIDATION_REPORT_FILE,
    )

    click.echo(report_text)
    click.echo(f"Transcript-to-gene mapping: {TRANSCRIPT_TO_GENE_FILE}")
    click.echo(f"Validation report:          {REFERENCE_VALIDATION_REPORT_FILE}")
    if report.problems:
        sys.exit(1)


@cli.group()
def database() -> None:
    """DuckDB persistence commands (Milestone 4)."""


@database.command("migrate")
def database_migrate() -> None:
    """Create/upgrade the atlas.duckdb schema. Safe to run repeatedly."""
    applied = apply_migrations(DATABASE_FILE)
    if applied:
        logger.info("Applied %d migration(s): %s", len(applied), ", ".join(applied))
        click.echo(f"Applied {len(applied)} migration(s): {', '.join(applied)}")
    else:
        click.echo("Database already up to date; no migrations applied.")
    click.echo(f"Database: {DATABASE_FILE}")


@database.command("load-genes")
def database_load_genes() -> None:
    """Load metadata/gene_master.tsv and gene_external_identifiers.tsv into DuckDB.

    Fully derived, deterministic tables: each run truncates and reloads
    (safe to re-run; nothing manually curated lives only in these two
    database tables).
    """
    apply_migrations(DATABASE_FILE)
    conn = duckdb.connect(str(DATABASE_FILE))
    try:
        n_genes = load_genes(conn, GENE_MASTER_FILE)
        n_gxi = load_gene_external_identifiers(conn, GENE_EXTERNAL_IDENTIFIERS_FILE)
    finally:
        conn.close()
    logger.info("Loaded %d genes and %d gene_external_identifiers rows into %s", n_genes, n_gxi, DATABASE_FILE)
    click.echo(f"Loaded {n_genes} genes, {n_gxi} gene_external_identifiers rows into {DATABASE_FILE}")


@database.command("load-discovery")
def database_load_discovery() -> None:
    """Load reports/discovery/{studies,samples,runs}.tsv into DuckDB.

    The "STORE METADATA" step of the discover -> store -> review -> approve
    -> queue -> process workflow (spec section 23). Upserts rather than
    replaces: a sample's pipeline_status/qc_status/quant_status/
    exclusion_reason are only set the first time that sample is seen, so a
    later re-discovery run never resets progress a sample has since made.
    """
    studies_path = DISCOVERY_DIR / "studies.tsv"
    samples_path = DISCOVERY_DIR / "samples.tsv"
    runs_path = DISCOVERY_DIR / "runs.tsv"
    for path in (studies_path, samples_path, runs_path):
        if not path.is_file():
            raise click.ClickException(f"Missing {path}. Run 'atlas discovery report' first.")

    apply_migrations(DATABASE_FILE)
    conn = duckdb.connect(str(DATABASE_FILE))
    try:
        n_datasets = load_datasets(conn, studies_path)
        n_samples = load_samples(conn, runs_path, samples_path)
    finally:
        conn.close()
    logger.info("Loaded %d datasets and %d samples into %s", n_datasets, n_samples, DATABASE_FILE)
    click.echo(f"Loaded {n_datasets} datasets, {n_samples} samples into {DATABASE_FILE}")


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
@click.option(
    "--max-results",
    default=5000,
    show_default=True,
    help="Upper bound passed to pysradb's search (metadata only; no FASTQ/SRA data is downloaded).",
)
@click.option(
    "--enrich-crossrefs/--no-enrich-crossrefs",
    default=False,
    show_default=True,
    help="Also resolve GEO/PMID cross-references per study (pysradb; can take a minute or more). "
    "DOI/publication title still need a further PMID lookup and are never resolved here.",
)
def discovery_report(max_results: int, enrich_crossrefs: bool) -> None:
    """Discover A. oryzae RNA-Seq metadata on NCBI SRA and write the discovery report.

    Metadata-only (PROJECT_MASTER_SPEC.md section 23: discovery and
    download are separate phases). Writes reports/discovery/studies.tsv,
    samples.tsv, runs.tsv, exclusions.tsv, discovery_<date>.md, and the raw
    search result under reports/discovery/raw_api_responses/. Nothing is
    marked RECOMMENDED_MVP automatically; see the report's "Next step".
    """
    DISCOVERY_RAW_API_RESPONSES_DIR.mkdir(parents=True, exist_ok=True)
    discovery_date = date.today().isoformat()
    raw_path = DISCOVERY_RAW_API_RESPONSES_DIR / f"sra_search_{discovery_date}.tsv"

    click.echo(f"Querying NCBI SRA (organism={sra_search.ORGANISM!r}, strategy={sra_search.STRATEGY!r}) ...")
    provenance = sra_search.run_search(raw_path, max_results=max_results)
    logger.info(
        "Discovery search: %s rows via %s %s -> %s",
        provenance.n_rows_returned,
        provenance.tool,
        provenance.tool_version,
        raw_path,
    )

    runs = load_discovered_runs(raw_path)
    tables = build_discovery_tables(runs, discovery_date=discovery_date)

    if enrich_crossrefs:
        study_accessions = sorted({s.study_accession for s in tables.studies if s.study_accession})
        click.echo(f"Resolving GEO/PMID cross-references for {len(study_accessions)} studies (this can take a while) ...")
        crossrefs = fetch_study_crossrefs(study_accessions)
        n_geo = sum(1 for c in crossrefs.values() if c.geo_accession)
        n_pmid = sum(1 for c in crossrefs.values() if c.pmid)
        logger.info("Cross-reference enrichment: %d/%d studies have a GEO hit, %d/%d have a PMID", n_geo, len(study_accessions), n_pmid, len(study_accessions))
        tables = replace(tables, studies=apply_crossrefs_to_studies(tables.studies, crossrefs))

    tsv_paths = write_discovery_tsvs(tables, DISCOVERY_DIR)
    report_text = render_markdown_report(tables, provenance, crossrefs_enriched=enrich_crossrefs)
    report_path = DISCOVERY_DIR / f"discovery_{discovery_date}.md"
    report_path.write_text(report_text, encoding="utf-8")
    logger.info(
        "Discovery report: %d studies, %d samples, %d runs (%d excluded) -> %s",
        len(tables.studies),
        len(tables.samples),
        len(tables.runs),
        len(tables.exclusions),
        report_path,
    )

    click.echo(report_text)
    click.echo(f"Raw API response:   {raw_path}")
    for name, path in tsv_paths.items():
        click.echo(f"{name.capitalize():<18} {path}")
    click.echo(f"Markdown report:    {report_path}")


@discovery.command("export")
def discovery_export() -> None:
    _not_implemented("Milestone 2 (Public transcriptome discovery report)", "atlas discovery export")


@cli.group()
def sample() -> None:
    """Per-sample approval/queueing commands (Milestone 4+)."""


@sample.command("approve")
@click.argument("srr")
@click.option(
    "--reason",
    default="",
    help="Why this sample is being approved (recorded in processing_events for audit).",
)
def sample_approve(srr: str, reason: str) -> None:
    """Approve a discovered sample for downloading/processing.

    The human sign-off gate between discovery and download/processing
    (PROJECT_MASTER_SPEC.md section 23); does not download or process
    anything itself. Requires the sample to already be loaded
    (`atlas discovery report` then `atlas database load-discovery`).
    """
    if not DATABASE_FILE.is_file():
        raise click.ClickException("No database found. Run 'atlas database migrate' first.")
    conn = duckdb.connect(str(DATABASE_FILE))
    try:
        try:
            result = approve_sample(conn, srr, reason=reason)
        except SampleNotFoundError:
            raise click.ClickException(
                f"Sample {srr} not found. Run 'atlas discovery report' and 'atlas database load-discovery' first."
            )
        except SampleExcludedError:
            raise click.ClickException(f"Sample {srr} is EXCLUDED and cannot be approved; see exclusions.tsv.")
    finally:
        conn.close()

    if result.already_approved:
        click.echo(f"Sample {srr} is already APPROVED.")
        return
    logger.info("Approved sample %s (was %s)%s", srr, result.previous_status, f": {reason}" if reason else "")
    click.echo(f"Approved {srr} (was {result.previous_status}).")


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


@process.command("ingest")
@click.argument("srr", required=False)
@click.option("--all", "ingest_all", is_flag=True, help="Ingest every results/<accession>/ folder with a DONE marker.")
def process_ingest(srr: str | None, ingest_all: bool) -> None:
    """Ingest a Colab-produced results/<accession>/ folder into the database.

    Reads gene_quant.tsv and fastp.json (docs/decisions/0004-colab-based-
    acquisition.md), loads them into gene_expression/sample_qc, and moves
    the sample's pipeline_status to QUANTIFIED. Safe to re-run: a sample's
    prior gene_expression/sample_qc rows are replaced, not duplicated.
    """
    if bool(srr) == ingest_all:
        raise click.ClickException("Pass exactly one of SRR or --all.")
    if not DATABASE_FILE.is_file():
        raise click.ClickException("No database found. Run 'atlas database migrate' first.")

    try:
        pipeline_version = str(load_pipeline_config().get("pipeline_version", ""))
    except ConfigError:
        pipeline_version = ""
    try:
        reference_version = str(load_reference_config().get("reference_version", ""))
    except ConfigError:
        reference_version = ""

    accessions = find_ingestable_accessions(RESULTS_DIR) if ingest_all else [srr]
    if ingest_all and not accessions:
        click.echo(f"No results with a DONE marker found under {RESULTS_DIR}.")
        return

    conn = duckdb.connect(str(DATABASE_FILE))
    try:
        for accession in accessions:
            try:
                result = ingest_sample_results(
                    conn, accession, RESULTS_DIR, pipeline_version=pipeline_version, reference_version=reference_version
                )
            except SampleNotFoundError:
                click.echo(f"{accession}: SKIPPED -- not found in database (run 'atlas database load-discovery' first).")
                continue
            except ResultsNotFoundError:
                click.echo(f"{accession}: SKIPPED -- no results/{accession}/ folder found.")
                continue
            except ResultsIncompleteError:
                click.echo(f"{accession}: SKIPPED -- results/{accession}/ has no DONE marker or gene_quant.tsv (incomplete).")
                continue
            logger.info(
                "Ingested %s (was %s): %d genes, %d qc metrics", accession, result.previous_status, result.n_genes, result.n_qc_metrics
            )
            click.echo(f"{accession}: ingested (was {result.previous_status}) -- {result.n_genes} genes, {result.n_qc_metrics} qc metrics.")
    finally:
        conn.close()


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
