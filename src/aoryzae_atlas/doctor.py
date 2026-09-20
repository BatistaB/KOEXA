"""`atlas doctor`: environment/sanity checks.

Distinguishes REQUIRED checks (missing config files, unwritable directories)
from OPTIONAL checks (external tools such as nextflow/salmon/docker that are
only needed once acquisition/quantification milestones begin). Never
fabricates a version number or path; a missing optional tool is reported as
missing, not silently skipped.
"""
from __future__ import annotations

import shutil
import sys
from dataclasses import dataclass

from . import __version__
from .config import ConfigError, load_pipeline_config, load_qc_config, load_reference_config, load_storage_config
from .paths import PROJECT_ROOT, REQUIRED_CONFIG_FILES, REQUIRED_DIRS


@dataclass
class CheckResult:
    name: str
    ok: bool
    required: bool
    detail: str


def _check_python_version() -> CheckResult:
    ok = sys.version_info >= (3, 10)
    return CheckResult(
        name="python_version",
        ok=ok,
        required=True,
        detail=f"{sys.version.split()[0]} ({'ok' if ok else 'need >= 3.10'})",
    )


def _check_dirs() -> list[CheckResult]:
    results = []
    for d in REQUIRED_DIRS:
        results.append(
            CheckResult(name=f"dir:{d.relative_to(PROJECT_ROOT)}", ok=d.is_dir(), required=True, detail=str(d))
        )
    return results


def _check_config_files() -> list[CheckResult]:
    results = []
    for f in REQUIRED_CONFIG_FILES:
        results.append(
            CheckResult(name=f"config:{f.name}", ok=f.is_file(), required=True, detail=str(f))
        )
    return results


def _check_config_parses() -> list[CheckResult]:
    results = []
    for label, loader in (
        ("reference.yaml", load_reference_config),
        ("pipeline.yaml", load_pipeline_config),
        ("qc.yaml", load_qc_config),
        ("storage.yaml", load_storage_config),
    ):
        try:
            loader()
            results.append(CheckResult(name=f"parse:{label}", ok=True, required=True, detail="parsed OK"))
        except ConfigError as exc:
            results.append(CheckResult(name=f"parse:{label}", ok=False, required=True, detail=str(exc)))
    return results


def _check_optional_tool(tool: str) -> CheckResult:
    path = shutil.which(tool)
    return CheckResult(
        name=f"tool:{tool}",
        ok=path is not None,
        required=False,
        detail=path or "not found on PATH (required before acquisition/quantification milestones)",
    )


def _check_reference_frozen() -> CheckResult:
    try:
        ref = load_reference_config()
        frozen = bool(ref.get("frozen", False))
    except ConfigError:
        frozen = False
    return CheckResult(
        name="reference_frozen",
        ok=True,  # informational, not a failure at Milestone 0
        required=False,
        detail="frozen" if frozen else "NOT frozen yet (expected before Milestone 3 completes)",
    )


def run_doctor() -> list[CheckResult]:
    results: list[CheckResult] = [_check_python_version()]
    results += _check_dirs()
    results += _check_config_files()
    results += _check_config_parses()
    for tool in ("git", "nextflow", "docker", "salmon", "pysradb"):
        results.append(_check_optional_tool(tool))
    results.append(_check_reference_frozen())
    return results


def doctor_report_text() -> tuple[str, bool]:
    """Return (report_text, all_required_ok)."""
    results = run_doctor()
    lines = [f"AOED doctor report (aoryzae_atlas {__version__})", f"Project root: {PROJECT_ROOT}", ""]
    all_required_ok = True
    for r in results:
        if r.required and not r.ok:
            all_required_ok = False
        marker = "OK  " if r.ok else ("FAIL" if r.required else "WARN")
        tag = "required" if r.required else "optional"
        lines.append(f"[{marker}] ({tag}) {r.name}: {r.detail}")
    lines.append("")
    lines.append("All required checks passed." if all_required_ok else "One or more REQUIRED checks failed.")
    return "\n".join(lines), all_required_ok
