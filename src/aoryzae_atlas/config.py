"""Typed-ish loading of the YAML configuration files under config/.

Kept deliberately simple (plain dicts) for Milestone 0. Do not invent
defaults for scientifically meaningful fields (e.g. reference accessions) -
missing values must stay None/null and callers must handle that explicitly,
per PROJECT_MASTER_SPEC.md section 3.1.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from .paths import CONFIG_DIR


class ConfigError(RuntimeError):
    """Raised when a required configuration file is missing or malformed."""


def _load_yaml_file(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise ConfigError(f"Missing required config file: {path}")
    with path.open("r", encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    if data is None:
        data = {}
    if not isinstance(data, dict):
        raise ConfigError(f"Expected a YAML mapping at top level of {path}")
    return data


def load_reference_config() -> dict[str, Any]:
    return _load_yaml_file(CONFIG_DIR / "reference.yaml")


def load_pipeline_config() -> dict[str, Any]:
    return _load_yaml_file(CONFIG_DIR / "pipeline.yaml")


def load_qc_config() -> dict[str, Any]:
    return _load_yaml_file(CONFIG_DIR / "qc.yaml")


def load_storage_config() -> dict[str, Any]:
    return _load_yaml_file(CONFIG_DIR / "storage.yaml")


def is_reference_frozen() -> bool:
    """Whether the canonical reference has been frozen (Milestone 3).

    Large-scale quantification must refuse to proceed while this is False.
    """
    try:
        ref = load_reference_config()
    except ConfigError:
        return False
    return bool(ref.get("frozen", False))
