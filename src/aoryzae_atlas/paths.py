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
