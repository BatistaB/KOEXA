"""Central definition of on-disk project layout.

Every other module resolves paths through this module rather than
hard-coding relative paths, so the project root can be located regardless
of the current working directory the CLI is invoked from.
"""
from __future__ import annotations

from pathlib import Path


def find_project_root(start: Path | None = None) -> Path:
    """Walk upward from `start` (default: this file) to find the repo root.

    The repo root is identified by the presence of PROJECT_MASTER_SPEC.md,
    which every AOED checkout must have at its top level.
    """
    here = (start or Path(__file__)).resolve()
    for candidate in [here, *here.parents]:
        if (candidate / "PROJECT_MASTER_SPEC.md").is_file():
            return candidate
    # Fallback: assume src/aoryzae_atlas/paths.py -> repo root is parents[2]
    return Path(__file__).resolve().parents[2]


PROJECT_ROOT = find_project_root()

CONFIG_DIR = PROJECT_ROOT / "config"
METADATA_DIR = PROJECT_ROOT / "metadata"
WORKFLOWS_DIR = PROJECT_ROOT / "workflows"
REFERENCE_DIR = PROJECT_ROOT / "reference"
SCRATCH_DIR = PROJECT_ROOT / "scratch"
NEXTFLOW_WORK_DIR = SCRATCH_DIR / "nextflow-work"
RUNTIME_DIR = PROJECT_ROOT / "runtime"
RUNTIME_STATUS_FILE = RUNTIME_DIR / "status.json"
RESULTS_DIR = PROJECT_ROOT / "results"
LOGS_DIR = RESULTS_DIR / "logs"
DATABASE_DIR = PROJECT_ROOT / "database"
DATABASE_FILE = DATABASE_DIR / "atlas.duckdb"
MATRICES_DIR = PROJECT_ROOT / "matrices"
ANALYSIS_DIR = PROJECT_ROOT / "analysis"
REPORTS_DIR = PROJECT_ROOT / "reports"
APP_DIR = PROJECT_ROOT / "app"

# Milestone 1 input evidence, as supplied by the user (see TODO.md). Not
# part of REQUIRED_DIRS/REQUIRED_CONFIG_FILES: it is real biological data
# the user placed on disk, not scaffolding `atlas init` should create.
FUNGIDB_V71_DIR = DATABASE_DIR / "FungiDB_v71"
UNIPROT_WORKBOOK_FILE = FUNGIDB_V71_DIR / "Archive_9_PSIM_Aory.xlsx"
FUNGIDB_PROTEIN_FASTA_FILE = FUNGIDB_V71_DIR / "FungiDB-71_AoryzaeRIB40_AnnotatedProteins.fasta"
FUNGIDB_GENE_ALIASES_FILE = FUNGIDB_V71_DIR / "FungiDB-71_AoryzaeRIB40_GeneAliases.txt"
FUNGIDB_GFF_FILE = FUNGIDB_V71_DIR / "FungiDB-71_AoryzaeRIB40.gff"
FUNGIDB_GENE_PRODUCT_UPDATES_FILE = FUNGIDB_V71_DIR / "FungiDB-71_AoryzaeRIB40_gene_product_updates_b71.txt"
FUNGIDB_GENOME_FASTA_FILE = FUNGIDB_V71_DIR / "FungiDB-71_AoryzaeRIB40_Genome.fasta"
FUNGIDB_TRANSCRIPT_FASTA_FILE = FUNGIDB_V71_DIR / "FungiDB-71_AoryzaeRIB40_AnnotatedTranscripts.fasta"
FUNGIDB_GO_GAF_FILE = FUNGIDB_V71_DIR / "FungiDB-71_AoryzaeRIB40_GO.gaf"

REFERENCE_VALIDATION_REPORT_FILE = REPORTS_DIR / "reference_validation.txt"
TRANSCRIPT_TO_GENE_FILE = REFERENCE_DIR / "transcripts" / "t2g.tsv"

GENE_ID_MAPPING_FILE = METADATA_DIR / "gene_id_mapping.tsv"
GENE_ID_MAPPING_REPORT_FILE = REPORTS_DIR / "gene_id_mapping_summary.txt"
GENE_EXTERNAL_IDENTIFIERS_FILE = METADATA_DIR / "gene_external_identifiers.tsv"
GENE_MASTER_FILE = METADATA_DIR / "gene_master.tsv"

CONDITIONS_FILE = METADATA_DIR / "conditions.tsv"
SAMPLES_CURATION_FILE = METADATA_DIR / "samples.tsv"
# BioProjects that are one study (see aoryzae_atlas.database.study_groups).
STUDY_GROUPS_FILE = METADATA_DIR / "study_groups.tsv"

# Study enrichment (`atlas annotate ...`): curated paper/summary/tags per
# study, the shared tag vocabulary, and the auto-collected evidence they
# are written from.
STUDY_ANNOTATIONS_DIR = METADATA_DIR / "study_annotations"
SAMPLE_TAG_VOCABULARY_FILE = METADATA_DIR / "sample_tag_vocabulary.tsv"
STUDY_EVIDENCE_DIR = REPORTS_DIR / "study_evidence"

DISCOVERY_DIR = REPORTS_DIR / "discovery"
DISCOVERY_RAW_API_RESPONSES_DIR = DISCOVERY_DIR / "raw_api_responses"

# Milestone 9/10/11 matrix + classification artifacts (`atlas matrix build`,
# `atlas stats genes`, `atlas entropy genes`, `atlas cluster genes`).
GENE_BY_SAMPLE_TPM_FILE = MATRICES_DIR / "tpm" / "gene_by_sample_tpm.parquet"
GENE_BY_CONDITION_TPM_FILE = MATRICES_DIR / "condition_aggregates" / "gene_by_condition_median_tpm.parquet"
SAMPLE_CONDITION_MAP_FILE = MATRICES_DIR / "condition_aggregates" / "sample_condition_map.parquet"

GENE_FEATURE_TABLE_FILE = ANALYSIS_DIR / "classification" / "gene_expression_behavior_established.parquet"
ENTROPY_TABLE_FILE = ANALYSIS_DIR / "entropy" / "gene_tsallis_hill.parquet"
CLASSIFICATION_FILE = ANALYSIS_DIR / "classification" / "gene_expression_behavior.parquet"
CLASSIFICATION_TSV_FILE = ANALYSIS_DIR / "classification" / "gene_expression_behavior.tsv.gz"
CLASSIFICATION_SUMMARY_FILE = REPORTS_DIR / "gene_expression_behavior_summary.md"

# Pan-transcriptomic expression rank (notebooks/gene_expression_classification.ipynb):
# one value per independent biosample, global distribution per gene, no per-study
# re-analysis. Separate files from the condition-level pipeline above on purpose.
GENE_BY_BIOSAMPLE_TPM_FILE = MATRICES_DIR / "tpm" / "gene_by_biosample_TPM.parquet"
EXPRESSION_RANK_FILE = ANALYSIS_DIR / "classification" / "gene_expression_rank.parquet"
EXPRESSION_RANK_TSV_FILE = ANALYSIS_DIR / "classification" / "gene_expression_rank.tsv.gz"
EXPRESSION_RANK_THRESHOLDS_FILE = ANALYSIS_DIR / "classification" / "gene_expression_rank_thresholds.tsv"
EXPRESSION_RANK_SUMMARY_FILE = ANALYSIS_DIR / "classification" / "gene_expression_rank_summary.json"
EXPRESSION_RANK_REPORT_FILE = REPORTS_DIR / "gene_expression_classification.md"

# Milestone 7 web bridge (`atlas app export-web`): JSON snapshots fetched at
# runtime by the React app (app/web/src/data/*). Gitignored -- regenerated,
# never hand-edited (see app/web/.gitignore).
WEB_DATA_DIR = APP_DIR / "web" / "public" / "data"

REQUIRED_DIRS = [
    CONFIG_DIR, METADATA_DIR, WORKFLOWS_DIR, REFERENCE_DIR, SCRATCH_DIR,
    NEXTFLOW_WORK_DIR, RUNTIME_DIR, RESULTS_DIR, LOGS_DIR, DATABASE_DIR,
    MATRICES_DIR, ANALYSIS_DIR, REPORTS_DIR, APP_DIR,
]

REQUIRED_CONFIG_FILES = [
    CONFIG_DIR / "reference.yaml",
    CONFIG_DIR / "pipeline.yaml",
    CONFIG_DIR / "qc.yaml",
    CONFIG_DIR / "storage.yaml",
]
