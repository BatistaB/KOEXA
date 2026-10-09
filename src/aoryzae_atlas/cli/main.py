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
import subprocess
import sys
from dataclasses import replace
from datetime import date, datetime, timezone
from pathlib import Path

import click
import duckdb
import pandas as pd

from .. import __version__
from ..annotation.evidence import collect_study_evidence, write_evidence
from ..annotation.ingest import AnnotationValidationError, load_study_annotations
from ..annotation.schema import load_all_annotations, validate_annotation
from ..annotation.vocabulary import load_vocabulary
from ..clustering.classify import classify_genes
from ..config import ConfigError, load_pipeline_config, load_reference_config, load_storage_config
from ..database.approve import (
    SampleExcludedError,
    SampleHasResultsError,
    SampleNotApprovedError,
    SampleNotFoundError,
    approve_sample,
    exclude_sample,
    unapprove_sample,
)
from ..database.ingest_conditions import load_conditions, load_sample_condition_links
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
from ..entropy.tsallis import compute_entropy_feature_table
from ..identifiers.external_identifiers import (
    from_gene_aliases_file,
    from_uniprot_mapping,
    write_external_identifiers_tsv,
)
from ..identifiers.reconcile import render_summary_report, run_reconciliation, write_mapping_tsv
from ..logging_setup import get_logger
from ..matrix.build import (
    collapse_technical_replicates,
    condition_level_stats,
    fetch_gene_sample_tpm,
    fetch_sample_condition_map,
    pivot_gene_by_condition,
    pivot_gene_by_sample,
)
from ..matrix.stats import compute_gene_feature_table
from ..metadata.gene_master import build_gene_master_rows, write_gene_master_tsv
from ..metadata.gene_product_updates import load_b71_products
from ..metadata.gff import load_protein_coding_genes
from ..state import SampleState
from ..paths import (
    APP_DIR,
    CLASSIFICATION_FILE,
    CLASSIFICATION_SUMMARY_FILE,
    CLASSIFICATION_TSV_FILE,
    CONDITIONS_FILE,
    DATABASE_FILE,
    DISCOVERY_DIR,
    DISCOVERY_RAW_API_RESPONSES_DIR,
    ENTROPY_TABLE_FILE,
    EXPRESSION_RANK_FILE,
    EXPRESSION_RANK_SUMMARY_FILE,
    EXPRESSION_RANK_THRESHOLDS_FILE,
    EXPRESSION_RANK_TSV_FILE,
    FUNGIDB_GENE_ALIASES_FILE,
    FUNGIDB_GENE_PRODUCT_UPDATES_FILE,
    FUNGIDB_GENOME_FASTA_FILE,
    FUNGIDB_GFF_FILE,
    FUNGIDB_PROTEIN_FASTA_FILE,
    FUNGIDB_TRANSCRIPT_FASTA_FILE,
    GENE_BY_BIOSAMPLE_TPM_FILE,
    GENE_BY_CONDITION_TPM_FILE,
    GENE_BY_SAMPLE_TPM_FILE,
    GENE_EXTERNAL_IDENTIFIERS_FILE,
    GENE_FEATURE_TABLE_FILE,
    GENE_ID_MAPPING_FILE,
    GENE_ID_MAPPING_REPORT_FILE,
    GENE_MASTER_FILE,
    PROJECT_ROOT,
    REFERENCE_VALIDATION_REPORT_FILE,
    REQUIRED_CONFIG_FILES,
    REQUIRED_DIRS,
    RESULTS_DIR,
    SAMPLES_CURATION_FILE,
    SAMPLE_CONDITION_MAP_FILE,
    SAMPLE_TAG_VOCABULARY_FILE,
    SCRATCH_DIR,
    STUDY_ANNOTATIONS_DIR,
    STUDY_EVIDENCE_DIR,
    TRANSCRIPT_TO_GENE_FILE,
    UNIPROT_WORKBOOK_FILE,
    WEB_DATA_DIR,
)
from ..reference.transcript_to_gene import load_transcript_to_gene, write_t2g_tsv
from ..reference.validate import render_validation_report, validate_reference
from ..runtime_status import init_runtime_status, load_runtime_status
from ..rank.pipeline import NoQuantifiedSamplesError, build_expression_rank, write_rank_outputs
from ..webexport.build import write_all as export_web_data

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


@database.command("load-conditions")
def database_load_conditions() -> None:
    """Load metadata/conditions.tsv and link curated samples to their condition_id.

    Milestone 6 (PROJECT_MASTER_SPEC.md section 37): "curate structured
    condition metadata" + "confirm sample/run/technical-replicate
    distinctions". Requires 'atlas database load-discovery' to have run
    first (samples must already exist before they can be linked to a
    condition).
    """
    for path in (CONDITIONS_FILE, SAMPLES_CURATION_FILE):
        if not path.is_file():
            raise click.ClickException(f"Missing {path}.")

    apply_migrations(DATABASE_FILE)
    conn = duckdb.connect(str(DATABASE_FILE))
    try:
        n_conditions = load_conditions(conn, CONDITIONS_FILE)
        n_links = load_sample_condition_links(conn, SAMPLES_CURATION_FILE)
    finally:
        conn.close()
    logger.info("Loaded %d conditions, linked %d samples in %s", n_conditions, n_links, DATABASE_FILE)
    click.echo(f"Loaded {n_conditions} conditions, linked {n_links} samples in {DATABASE_FILE}")


@database.command("load-annotations")
def database_load_annotations() -> None:
    """Load metadata/study_annotations/*.json + the tag vocabulary into DuckDB.

    Truncate-and-reload of study_annotations / sample_tags / tag_vocabulary.
    Every file is validated first (see 'atlas annotate validate'); any
    problem aborts the load so the database never holds a partial set.
    """
    for path in (SAMPLE_TAG_VOCABULARY_FILE, SAMPLES_CURATION_FILE):
        if not path.is_file():
            raise click.ClickException(f"Missing {path}.")
    apply_migrations(DATABASE_FILE)
    conn = duckdb.connect(str(DATABASE_FILE))
    try:
        n_studies, n_tags = load_study_annotations(
            conn, STUDY_ANNOTATIONS_DIR, SAMPLE_TAG_VOCABULARY_FILE, SAMPLES_CURATION_FILE
        )
    except AnnotationValidationError as exc:
        raise click.ClickException(str(exc)) from exc
    finally:
        conn.close()
    logger.info("Loaded %d study annotations, %d sample-tag rows into %s", n_studies, n_tags, DATABASE_FILE)
    click.echo(f"Loaded {n_studies} study annotations, {n_tags} sample-tag rows into {DATABASE_FILE}")


@cli.group()
def annotate() -> None:
    """Study enrichment: associated paper, short design summary, per-sample tags.

    Workflow for a new study (also run by 'atlas refresh'):
    'annotate collect' gathers accession-linked paper candidates and the
    study's metadata into reports/study_evidence/<BIOPROJECT>.json; a curator
    (human or agent -- see .claude/skills/annotate-study/SKILL.md) writes
    metadata/study_annotations/<BIOPROJECT>.json from it; 'annotate validate'
    checks it against the shared tag vocabulary.
    """


def _studies_in_curation() -> list[str]:
    samples = pd.read_csv(SAMPLES_CURATION_FILE, sep="\t", dtype=str, keep_default_na=False)
    return sorted(set(samples["bioproject"]) - {""})


@annotate.command("collect")
@click.argument("bioprojects", nargs=-1)
@click.option("--missing", "only_missing", is_flag=True, help="Only studies with no evidence file yet.")
def annotate_collect(bioprojects: tuple[str, ...], only_missing: bool) -> None:
    """Fetch paper candidates + study metadata into reports/study_evidence/.

    Metadata only (NCBI E-utilities, Europe PMC); never downloads reads.
    With no BIOPROJECTS, every study in metadata/samples.tsv is considered.
    """
    targets = list(bioprojects) or _studies_in_curation()
    if only_missing:
        targets = [bp for bp in targets if not (STUDY_EVIDENCE_DIR / f"{bp}.json").is_file()]
    if not targets:
        click.echo("No study needs evidence collection.")
        return
    failures = []
    for bioproject in targets:
        try:
            evidence = collect_study_evidence(bioproject, DISCOVERY_DIR, CONDITIONS_FILE, SAMPLES_CURATION_FILE)
        except OSError as exc:  # network failure: report, keep going
            failures.append(bioproject)
            click.echo(f"{bioproject}: FAILED ({exc})")
            continue
        path = write_evidence(evidence, STUDY_EVIDENCE_DIR)
        top = evidence["paper_candidates"][0] if evidence["paper_candidates"] else None
        best = f"{top['pmid']} {top['title'][:70]}" if top else "no accession-linked paper"
        click.echo(f"{bioproject}: {evidence['suggested_paper_status']:<9} {best}  -> {path.name}")
        logger.info("annotate collect %s: %s candidates, suggested %s", bioproject,
                    len(evidence["paper_candidates"]), evidence["suggested_paper_status"])
    if failures:
        raise click.ClickException(f"Evidence collection failed for {', '.join(failures)} (network?).")


@annotate.command("status")
def annotate_status() -> None:
    """Which studies have evidence collected / a curated annotation."""
    annotated = {a.bioproject: a for a in load_all_annotations(STUDY_ANNOTATIONS_DIR)}
    pending = []
    for bioproject in _studies_in_curation():
        has_evidence = (STUDY_EVIDENCE_DIR / f"{bioproject}.json").is_file()
        annotation = annotated.get(bioproject)
        state = f"annotated (paper {annotation.paper.get('status')})" if annotation else "NEEDS CURATION"
        if not annotation:
            pending.append(bioproject)
        click.echo(f"{bioproject:<14} evidence={'yes' if has_evidence else 'no ':<3}  {state}")
    if pending:
        click.echo(f"\n{len(pending)} study(ies) need an annotation: {', '.join(pending)}")


@annotate.command("validate")
def annotate_validate() -> None:
    """Check every annotation file against the vocabulary and metadata/samples.tsv."""
    vocabulary = load_vocabulary(SAMPLE_TAG_VOCABULARY_FILE)
    samples = pd.read_csv(SAMPLES_CURATION_FILE, sep="\t", dtype=str, keep_default_na=False)
    annotations = load_all_annotations(STUDY_ANNOTATIONS_DIR)
    problems = [p for a in annotations for p in validate_annotation(a, vocabulary, samples)]
    for problem in problems:
        click.echo(problem)
    if problems:
        raise click.ClickException(f"{len(problems)} problem(s) in {len(annotations)} annotation file(s).")
    click.echo(f"{len(annotations)} annotation file(s) valid; vocabulary has {len(vocabulary.entries)} tags.")


@annotate.command("suggest")
@click.argument("text")
def annotate_suggest(text: str) -> None:
    """Existing tags resembling TEXT -- run before adding a new vocabulary tag."""
    vocabulary = load_vocabulary(SAMPLE_TAG_VOCABULARY_FILE)
    reason = vocabulary.check(text)
    click.echo(f"'{text}' is a valid tag ({vocabulary.category(text)})." if reason is None else reason)
    for tag in vocabulary.suggest(text):
        entry = vocabulary.entries[tag]
        click.echo(f"  {tag:<28} [{entry.category}] {entry.description}")


@cli.command()
@click.pass_context
def refresh(ctx: click.Context) -> None:
    """Standardized one-command update: DB reload -> ingest -> matrix -> classify -> export-web.

    Run this every time you add studies/samples to the atlas (new Colab
    results, updated metadata/conditions.tsv or samples.tsv, a re-run
    'atlas discovery report'). It chains, in order:

        database migrate -> database load-genes -> database load-discovery
        -> database load-conditions -> process ingest --all -> matrix build
        -> stats genes -> entropy genes -> cluster genes -> rank genes
        -> app export-web

    Every step is idempotent and safe to re-run. A step whose required
    input doesn't exist yet (e.g. no reports/discovery/*.tsv before the
    first 'atlas discovery report') is reported as SKIPPED, not treated as
    a fatal error -- this command always does as much as it currently can
    with whatever is on disk, rather than requiring every upstream step to
    have been run first.
    """
    steps: list[tuple[str, click.Command, dict]] = [
        ("database migrate", database_migrate, {}),
        ("database load-genes", database_load_genes, {}),
        ("database load-discovery", database_load_discovery, {}),
        ("database load-conditions", database_load_conditions, {}),
        ("annotate collect --missing", annotate_collect, {"bioprojects": (), "only_missing": True}),
        ("database load-annotations", database_load_annotations, {}),
        ("process ingest --all", process_ingest, {"srr": None, "ingest_all": True}),
        ("matrix build", matrix_build, {}),
        ("stats genes", stats_genes, {}),
        ("entropy genes", entropy_genes, {}),
        ("cluster genes", cluster_genes, {}),
        ("rank genes", rank_genes, {"no_robustness": False}),
        ("app export-web", app_export_web, {}),
    ]
    n_ok, n_skipped = 0, 0
    for label, command, kwargs in steps:
        click.echo(f"\n=== atlas {label} ===")
        try:
            ctx.invoke(command, **kwargs)
            n_ok += 1
        except click.ClickException as exc:
            click.echo(f"SKIPPED: {exc.format_message()}")
            n_skipped += 1
    click.echo(f"\nrefresh complete: {n_ok} step(s) ran, {n_skipped} skipped.")
    annotated = {a.bioproject for a in load_all_annotations(STUDY_ANNOTATIONS_DIR)}
    pending = [bp for bp in _studies_in_curation() if bp not in annotated]
    if pending:
        click.echo(
            f"NOTE: {len(pending)} study(ies) have no curated annotation yet: {', '.join(pending)}\n"
            "      Curate metadata/study_annotations/<BIOPROJECT>.json (see .claude/skills/annotate-study/SKILL.md)."
        )


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


@sample.command("unapprove")
@click.argument("srr")
@click.option(
    "--reason",
    required=True,
    help="Why the approval is being withdrawn (recorded in processing_events for audit).",
)
def sample_unapprove(srr: str, reason: str) -> None:
    """Return an APPROVED sample to METADATA_REVIEW (e.g. its raw data is not downloadable)."""
    if not DATABASE_FILE.is_file():
        raise click.ClickException("No database found. Run 'atlas database migrate' first.")
    conn = duckdb.connect(str(DATABASE_FILE))
    try:
        try:
            unapprove_sample(conn, srr, reason=reason)
        except SampleNotFoundError:
            raise click.ClickException(f"Sample {srr} not found.")
        except SampleNotApprovedError as exc:
            raise click.ClickException(f"Cannot unapprove: {exc}.")
    finally:
        conn.close()
    logger.info("Unapproved sample %s: %s", srr, reason)
    click.echo(f"Unapproved {srr} (now METADATA_REVIEW).")


@sample.command("exclude")
@click.argument("srr")
@click.option(
    "--reason",
    required=True,
    help="Why the sample is unusable (stored in samples.exclusion_reason and processing_events).",
)
def sample_exclude(srr: str, reason: str) -> None:
    """Exclude a sample from the atlas for good (e.g. a platform the pipeline cannot quantify)."""
    if not DATABASE_FILE.is_file():
        raise click.ClickException("No database found. Run 'atlas database migrate' first.")
    conn = duckdb.connect(str(DATABASE_FILE))
    try:
        try:
            changed = exclude_sample(conn, srr, reason=reason)
        except SampleNotFoundError:
            raise click.ClickException(f"Sample {srr} not found.")
        except SampleHasResultsError:
            raise click.ClickException(f"Sample {srr} already has expression results in the atlas; remove them first.")
    finally:
        conn.close()
    if changed:
        logger.info("Excluded sample %s: %s", srr, reason)
        click.echo(f"Excluded {srr}.")
    else:
        click.echo(f"Sample {srr} is already EXCLUDED.")


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
            except SampleExcludedError:
                click.echo(f"{accession}: SKIPPED -- sample is EXCLUDED from the atlas.")
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
    """Build gene x sample and gene x condition TPM matrices from DuckDB.

    Sample-level TPM (gene_expression, untouched) -> collapse technical
    replicates (mean) -> aggregate biological replicates per condition
    (median) -- see matrix/build.py's module docstring. Writes three
    parquet files under matrices/; every downstream command (stats/
    entropy/cluster genes) reads the condition matrix from here rather
    than re-querying DuckDB, so they all see the exact same snapshot.
    """
    if not DATABASE_FILE.is_file():
        raise click.ClickException("No database found. Run 'atlas database migrate' first.")

    conn = duckdb.connect(str(DATABASE_FILE), read_only=True)
    try:
        long_df = fetch_gene_sample_tpm(conn)
        sample_map = fetch_sample_condition_map(conn)
    finally:
        conn.close()

    if long_df.empty:
        raise click.ClickException("No QUANTIFIED samples in the database yet; nothing to build.")

    gene_by_sample = pivot_gene_by_sample(long_df)
    replicate_df = collapse_technical_replicates(long_df, sample_map)
    condition_stats = condition_level_stats(replicate_df)
    gene_by_condition = pivot_gene_by_condition(condition_stats)

    GENE_BY_SAMPLE_TPM_FILE.parent.mkdir(parents=True, exist_ok=True)
    GENE_BY_CONDITION_TPM_FILE.parent.mkdir(parents=True, exist_ok=True)
    gene_by_sample.to_parquet(GENE_BY_SAMPLE_TPM_FILE)
    gene_by_condition.to_parquet(GENE_BY_CONDITION_TPM_FILE)
    sample_map.to_parquet(SAMPLE_CONDITION_MAP_FILE)

    logger.info(
        "matrix build: %d genes x %d samples, %d genes x %d conditions",
        *gene_by_sample.shape, *gene_by_condition.shape,
    )
    click.echo(f"Gene x sample matrix:    {gene_by_sample.shape[0]:,} genes x {gene_by_sample.shape[1]} samples -> {GENE_BY_SAMPLE_TPM_FILE}")
    click.echo(f"Gene x condition matrix: {gene_by_condition.shape[0]:,} genes x {gene_by_condition.shape[1]} conditions -> {GENE_BY_CONDITION_TPM_FILE}")
    click.echo(f"Sample/condition map:    {len(sample_map)} curated samples -> {SAMPLE_CONDITION_MAP_FILE}")


@cli.group(name="app")
def app_group() -> None:
    """AOED interactive application commands (Milestone 7)."""


@app_group.command("serve")
def app_serve() -> None:
    _not_implemented("Milestone 7 (AOED basic interface)", "atlas app serve")


@app_group.command("export-web")
def app_export_web() -> None:
    """Export DuckDB + classification artifacts to app/web/public/data/*.json.

    Only samples that are QUANTIFIED and condition-curated are exported
    (see webexport.build.CURATED_QUANTIFIED_FILTER); the gene catalog
    (genes.json) is refreshed too, via app/web/scripts/export_gene_catalog.py.
    Safe to re-run: every file here is fully overwritten, never merged.
    """
    if not DATABASE_FILE.is_file():
        raise click.ClickException("No database found. Run 'atlas database migrate' first.")

    conn = duckdb.connect(str(DATABASE_FILE), read_only=True)
    try:
        summary = export_web_data(conn)
    finally:
        conn.close()

    gene_catalog_script = APP_DIR / "web" / "scripts" / "export_gene_catalog.py"
    if gene_catalog_script.is_file():
        result = subprocess.run(
            [sys.executable, str(gene_catalog_script)], cwd=PROJECT_ROOT, capture_output=True, text=True
        )
        if result.stdout:
            click.echo(result.stdout.rstrip())
        if result.returncode != 0:
            click.echo(result.stderr, err=True)
            raise click.ClickException("app/web/scripts/export_gene_catalog.py failed.")

    logger.info("app export-web: %s", summary)
    click.echo(f"Datasets:       {summary['n_datasets']} ({summary['datasets_bytes'] / 1024:.0f} KB)")
    click.echo(f"Conditions:     {summary['n_conditions']} ({summary['conditions_bytes'] / 1024:.0f} KB)")
    click.echo(f"Samples:        {summary['n_samples']} ({summary['samples_bytes'] / 1024:.0f} KB)")
    click.echo(f"Sample QC:      {summary['n_sample_qc']} ({summary['sample_qc_bytes'] / 1024:.0f} KB)")
    click.echo(f"Expression:     {summary['n_expression_rows']:,} rows ({summary['expression_bytes'] / 1024:.0f} KB)")
    if summary["n_classification_rows"]:
        click.echo(f"Classification: {summary['n_classification_rows']:,} genes ({summary['classification_bytes'] / 1024:.0f} KB)")
    else:
        click.echo("Classification: not exported (run 'atlas cluster genes' first)")
    if summary.get("n_expression_rank_rows"):
        click.echo(f"Expression rank: {summary['n_expression_rank_rows']:,} genes ({summary['expression_rank_bytes'] / 1024:.0f} KB)")
    else:
        click.echo("Expression rank: not exported (run 'atlas rank genes' first)")
    if summary["n_chromosome_bins"]:
        click.echo(f"Chromosome map: {summary['n_chromosome_bins']:,} bins ({summary['chromosome_expression_bytes'] / 1024:.0f} KB)")
    else:
        click.echo("Chromosome map: not exported (run 'atlas stats genes' first)")
    if summary.get("n_annotated_studies"):
        click.echo(f"Study annotations: {summary['n_annotated_studies']} studies ({summary['study_annotations_bytes'] / 1024:.0f} KB)")
    else:
        click.echo("Study annotations: not exported (run 'atlas database load-annotations' first)")
    click.echo(f"-> {WEB_DATA_DIR}")


@cli.group()
def stats() -> None:
    """Gene-level statistics commands (Milestone 9)."""


@stats.command("genes")
def stats_genes() -> None:
    """Compute the established per-gene feature table (abundance, prevalence,
    variability, Tau, Gini) from the condition matrix. No cluster_id/
    biological_label yet -- see 'atlas cluster genes' for that.
    """
    if not GENE_BY_CONDITION_TPM_FILE.is_file():
        raise click.ClickException("No condition matrix found. Run 'atlas matrix build' first.")
    gene_by_condition = pd.read_parquet(GENE_BY_CONDITION_TPM_FILE)
    feature_table = compute_gene_feature_table(gene_by_condition)

    GENE_FEATURE_TABLE_FILE.parent.mkdir(parents=True, exist_ok=True)
    feature_table.to_parquet(GENE_FEATURE_TABLE_FILE)

    logger.info("stats genes: %d genes x %d feature columns -> %s", *feature_table.shape, GENE_FEATURE_TABLE_FILE)
    click.echo(f"Wrote {feature_table.shape[0]:,} genes x {feature_table.shape[1]} feature columns -> {GENE_FEATURE_TABLE_FILE}")


@cli.group()
def entropy() -> None:
    """Tsallis/Hill diversity commands (Milestone 10, secondary/exploratory)."""


@entropy.command("genes")
def entropy_genes() -> None:
    """Compute per-gene Tsallis/Hill entropy (D_q) across conditions.

    Secondary/exploratory (see entropy/tsallis.py module docstring): kept
    available and unit-tested, not used by the standard classification
    pipeline's clustering step (see clustering/classify.py for why).
    """
    if not GENE_BY_CONDITION_TPM_FILE.is_file():
        raise click.ClickException("No condition matrix found. Run 'atlas matrix build' first.")
    gene_by_condition = pd.read_parquet(GENE_BY_CONDITION_TPM_FILE)
    entropy_table = compute_entropy_feature_table(gene_by_condition)

    ENTROPY_TABLE_FILE.parent.mkdir(parents=True, exist_ok=True)
    entropy_table.to_parquet(ENTROPY_TABLE_FILE)

    logger.info("entropy genes: %d genes x %d columns -> %s", *entropy_table.shape, ENTROPY_TABLE_FILE)
    click.echo(f"Wrote {entropy_table.shape[0]:,} genes x {entropy_table.shape[1]} entropy columns -> {ENTROPY_TABLE_FILE}")


@cli.group()
def cluster() -> None:
    """Clustering commands (Milestone 11)."""


@cluster.command("genes")
def cluster_genes() -> None:
    """Classify genes into BASE-model clusters + biological_label.

    Runs the standardized pipeline in clustering/classify.py (KMeans, k
    selected by silhouette over k=2..10, the same cautious threshold-based
    biological_label rule validated in
    notebooks/gene_expression_classification.ipynb). Writes the final
    gene_expression_behavior parquet/tsv.gz and a short markdown summary.
    Does NOT recompute the EXTENDED (Tsallis q-spectrum) model or cluster-
    stability diagnostics (subsampling/bootstrap/leave-one-study-out ARI) --
    those stay notebook-only; see classify.py's module docstring for why.
    """
    if not GENE_BY_CONDITION_TPM_FILE.is_file():
        raise click.ClickException("No condition matrix found. Run 'atlas matrix build' first.")
    gene_by_condition = pd.read_parquet(GENE_BY_CONDITION_TPM_FILE)
    result = classify_genes(gene_by_condition)

    GENE_FEATURE_TABLE_FILE.parent.mkdir(parents=True, exist_ok=True)
    result.feature_table.to_parquet(GENE_FEATURE_TABLE_FILE)
    ENTROPY_TABLE_FILE.parent.mkdir(parents=True, exist_ok=True)
    result.entropy_table.to_parquet(ENTROPY_TABLE_FILE)
    CLASSIFICATION_FILE.parent.mkdir(parents=True, exist_ok=True)
    result.final_table.to_parquet(CLASSIFICATION_FILE)
    result.final_table.to_csv(CLASSIFICATION_TSV_FILE, sep="\t", compression="gzip")

    counts = result.final_table["biological_label"].value_counts(dropna=False)
    summary_lines = [
        "# Gene expression behavior classification -- standardized pipeline summary",
        "",
        f"Generated by `atlas cluster genes`. K_BASE = {result.k_base} (silhouette-selected, k=2..10).",
        "",
        "## biological_label counts",
        "",
        counts.rename("n_genes").to_frame().to_markdown(),
        "",
        "This is the automated pipeline's output: BASE model only (abundance, "
        "prevalence, variability, Tau), no EXTENDED q-spectrum model and no "
        "cluster-stability diagnostics. For the full methodological writeup "
        "(Tau distributions, cross-method agreement, subsampling/bootstrap/"
        "leave-one-study-out stability), see "
        "notebooks/gene_expression_classification.ipynb and "
        "reports/gene_expression_classification.md.",
    ]
    CLASSIFICATION_SUMMARY_FILE.parent.mkdir(parents=True, exist_ok=True)
    CLASSIFICATION_SUMMARY_FILE.write_text("\n".join(summary_lines), encoding="utf-8")

    logger.info("cluster genes: K_BASE=%d, %s", result.k_base, dict(counts))
    click.echo(f"K_BASE = {result.k_base}")
    click.echo(counts.to_string())
    click.echo(f"Wrote {CLASSIFICATION_FILE}")
    click.echo(f"Wrote {CLASSIFICATION_TSV_FILE}")
    click.echo(f"Wrote {CLASSIFICATION_SUMMARY_FILE}")


@cli.group()
def rank() -> None:
    """Pan-transcriptomic expression rank: global gene behavior across ALL samples."""


@rank.command("genes")
@click.option("--no-robustness", is_flag=True, help="Skip the leave-one-study/strain-out robustness runs (faster).")
def rank_genes(no_robustness: bool) -> None:
    """Classify every gene by its global expression behavior across all independent samples.

    Unit of analysis = biosample (runs of one biosample are averaged); no per-study differential
    expression and no condition curation needed. Writes the per-gene table (parquet + tsv.gz),
    the quantile-derived thresholds, a scope/robustness summary (read by the web export) and the
    genes x biosamples TPM matrix. Re-run (or just run 'atlas refresh') whenever samples are added:
    every threshold is re-derived from the current atlas.

    The logic lives in aoryzae_atlas/rank/pipeline.py -- the notebook
    notebooks/gene_expression_classification.ipynb checks itself against that same function.
    """
    if not DATABASE_FILE.is_file():
        raise click.ClickException("No database found. Run 'atlas database migrate' first.")
    conn = duckdb.connect(str(DATABASE_FILE), read_only=True)
    try:
        result = build_expression_rank(conn, with_robustness=not no_robustness)
    except NoQuantifiedSamplesError as exc:
        raise click.ClickException(str(exc)) from exc
    finally:
        conn.close()

    write_rank_outputs(
        result,
        parquet_path=EXPRESSION_RANK_FILE,
        tsv_gz_path=EXPRESSION_RANK_TSV_FILE,
        thresholds_path=EXPRESSION_RANK_THRESHOLDS_FILE,
        summary_path=EXPRESSION_RANK_SUMMARY_FILE,
        biosample_matrix_path=GENE_BY_BIOSAMPLE_TPM_FILE,
    )
    scope = result.scope
    logger.info("rank genes: %d genes, %d samples, %s", scope["n_genes"], scope["n_samples"], scope["class_counts"])
    click.echo(
        f"{scope['n_genes']:,} genes over {scope['n_samples']} independent samples "
        f"({scope['n_runs']} runs, {scope['n_studies']} studies, {scope['n_strains']} strains)"
    )
    for name, count in scope["class_counts"].items():
        click.echo(f"  {name:<20} {count:>6,}  ({count / scope['n_genes']:.1%})")
    if scope["median_robustness_agreement"] is not None:
        click.echo(f"median class agreement under leave-one-study/strain-out: {scope['median_robustness_agreement']:.0%}")
    click.echo(f"Wrote {EXPRESSION_RANK_FILE}")


@cli.group()
def report() -> None:
    """Report-generation commands."""


@report.command("build")
def report_build() -> None:
    _not_implemented("Milestone 12 (Advanced AOED report)", "atlas report build")


if __name__ == "__main__":
    cli()
