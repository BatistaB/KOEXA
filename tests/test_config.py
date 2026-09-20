"""Tests for aoryzae_atlas.config (spec section 3.1: no invented defaults)."""
from __future__ import annotations

import pytest

from aoryzae_atlas import config


def test_load_reference_config_has_no_invented_accessions():
    ref = config.load_reference_config()
    assert ref["organism"] == "Aspergillus oryzae"
    assert ref["reference_strain"] == "RIB40"
    assert ref["canonical_gene_id_system"] == "AO09"
    # These must stay unpopulated until Milestone 3 verifies them.
    assert ref["assembly_accession"] is None
    assert ref["annotation_accession"] is None
    assert ref["reference_version"] is None
    assert ref["frozen"] is False


def test_is_reference_frozen_false_by_default():
    assert config.is_reference_frozen() is False


def test_load_pipeline_config_pins_versions():
    pipeline = config.load_pipeline_config()
    assert pipeline["nf_core_fetchngs"]["revision"]
    assert pipeline["nf_core_rnaseq"]["revision"]
    assert pipeline["nextflow"]["min_version"]


def test_load_storage_config_has_safety_margins():
    storage = config.load_storage_config()
    assert storage["storage"]["max_parallel_samples"] == 1
    assert storage["storage"]["minimum_free_gb"] > 0


def test_missing_config_file_raises_config_error(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "CONFIG_DIR", tmp_path)
    with pytest.raises(config.ConfigError):
        config.load_reference_config()


def test_non_mapping_yaml_raises_config_error(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "CONFIG_DIR", tmp_path)
    (tmp_path / "reference.yaml").write_text("- just\n- a\n- list\n", encoding="utf-8")
    with pytest.raises(config.ConfigError):
        config.load_reference_config()
