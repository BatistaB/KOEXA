"""Tests for aoryzae_atlas.annotation (study enrichment: paper, summary, sample tags)."""
from __future__ import annotations

import json

import duckdb
import pandas as pd
import pytest

from aoryzae_atlas.annotation.evidence import deposition_snippets
from aoryzae_atlas.annotation.ingest import AnnotationValidationError, load_study_annotations
from aoryzae_atlas.annotation.schema import load_annotation, validate_annotation
from aoryzae_atlas.annotation.vocabulary import VocabularyError, load_vocabulary
from aoryzae_atlas.database.migrate import apply_migrations
from aoryzae_atlas.paths import SAMPLE_TAG_VOCABULARY_FILE, SAMPLES_CURATION_FILE, STUDY_ANNOTATIONS_DIR

VOCAB = (
    "tag\tcategory\tdescription\tsynonyms\n"
    "submerged\tculture_system\tLiquid culture.\tliquid_culture;liquid\n"
    "glucose\tcarbon_source\tGlucose supplied.\tdextrose\n"
    "control\trole\tReference group.\t\n"
    "treated\trole\tTreated group.\t\n"
)
SAMPLES = (
    "sample_id\tbioproject\tcondition_id\n"
    "RUN1\tPRJTEST\tPRJTEST_ctrl\n"
    "RUN2\tPRJTEST\tPRJTEST_ctrl\n"
    "RUN3\tPRJTEST\tPRJTEST_trt\n"
    "OTHER\tPRJOTHER\tPRJOTHER_x\n"
)


def _tag(tag, source="paper_methods", confidence="high"):
    return {"tag": tag, "source": source, "confidence": confidence}


def _annotation(**overrides):
    doc = {
        "schema_version": 1,
        "bioproject": "PRJTEST",
        "paper": {"status": "found", "title": "A paper", "year": 2020, "doi": "10.1/x", "access": "full_text",
                  "association_evidence": "deposited under PRJTEST"},
        "study_summary": {"objective": "o", "experimental_design": "d", "main_finding": "f"},
        "tag_sets": {"common": [_tag("submerged"), _tag("glucose", "sample_metadata")]},
        "conditions": {
            "PRJTEST_ctrl": {"sets": ["common"], "tags": [_tag("control")]},
            "PRJTEST_trt": {"sets": ["common"], "tags": [_tag("treated"), _tag("30C"), _tag("3h_post_treatment")]},
        },
        "sample_tags": {"RUN3": [_tag("del_faaA", "sample_metadata")]},
    }
    doc.update(overrides)
    return doc


@pytest.fixture
def env(tmp_path):
    vocab_path = tmp_path / "vocab.tsv"
    vocab_path.write_text(VOCAB, encoding="utf-8")
    samples_path = tmp_path / "samples.tsv"
    samples_path.write_text(SAMPLES, encoding="utf-8")
    annotations_dir = tmp_path / "study_annotations"
    annotations_dir.mkdir()
    return vocab_path, samples_path, annotations_dir


def _write(annotations_dir, doc):
    path = annotations_dir / f"{doc['bioproject']}.json"
    path.write_text(json.dumps(doc), encoding="utf-8")
    return path


def _problems(env, doc):
    vocab_path, samples_path, annotations_dir = env
    samples = pd.read_csv(samples_path, sep="\t", dtype=str, keep_default_na=False)
    return validate_annotation(load_annotation(_write(annotations_dir, doc)), load_vocabulary(vocab_path), samples)


def test_vocabulary_accepts_vocab_and_parametric_tags(env):
    vocab = load_vocabulary(env[0])
    for tag in ("submerged", "30C", "24h", "3h_post_treatment", "ph_5_5", "strain_rib40", "del_faaA", "oe_cutL1"):
        assert vocab.check(tag) is None, tag
    assert vocab.category("30C") == "temperature"
    assert vocab.category("3h_post_treatment") == "time"


def test_vocabulary_rejects_synonym_and_names_the_canonical_tag(env):
    reason = load_vocabulary(env[0]).check("liquid_culture")
    assert reason is not None and "'submerged'" in reason


def test_vocabulary_suggests_similar_existing_tags(env):
    assert "submerged" in load_vocabulary(env[0]).suggest("submerged culture")


def test_vocabulary_rejects_synonym_that_is_also_a_tag(tmp_path):
    path = tmp_path / "v.tsv"
    path.write_text("tag\tcategory\tdescription\tsynonyms\na\tx\td\tb\nb\tx\td\t\n", encoding="utf-8")
    with pytest.raises(VocabularyError):
        load_vocabulary(path)


def test_valid_annotation_has_no_problems(env):
    assert _problems(env, _annotation()) == []


def test_unknown_tag_bad_source_and_confidence_are_reported(env):
    doc = _annotation()
    doc["conditions"]["PRJTEST_ctrl"]["tags"] = [{"tag": "glucose_PRJTEST", "source": "guess", "confidence": "sure"}]
    problems = _problems(env, doc)
    assert any("glucose_PRJTEST" in p for p in problems)
    assert any("source 'guess'" in p for p in problems)
    assert any("confidence 'sure'" in p for p in problems)


def test_found_paper_requires_evidence_and_identifier(env):
    doc = _annotation(paper={"status": "found", "title": "t", "year": 2020, "access": "full_text"})
    problems = _problems(env, doc)
    assert any("association_evidence" in p for p in problems)
    assert any("doi/pmid/url" in p for p in problems)


def test_not_found_paper_needs_no_bibliography(env):
    assert _problems(env, _annotation(paper={"status": "not_found"})) == []


def test_every_study_sample_must_resolve_to_tags(env):
    doc = _annotation()
    del doc["conditions"]["PRJTEST_trt"]
    doc["sample_tags"] = {}
    problems = _problems(env, doc)
    assert any("RUN3" in p and "resolves to no tags" in p for p in problems)


def test_conditions_and_sample_tags_must_belong_to_the_study(env):
    doc = _annotation()
    doc["conditions"]["PRJOTHER_x"] = {"tags": [_tag("control")]}
    doc["sample_tags"]["OTHER"] = [_tag("control")]
    problems = _problems(env, doc)
    assert any("PRJOTHER_x" in p for p in problems)
    assert any("unknown sample 'OTHER'" in p for p in problems)


def test_load_resolves_sets_condition_and_run_tags(env, tmp_path):
    vocab_path, samples_path, annotations_dir = env
    _write(annotations_dir, _annotation())
    db_path = tmp_path / "t.duckdb"
    apply_migrations(db_path)
    conn = duckdb.connect(str(db_path))
    try:
        n_studies, n_tags = load_study_annotations(conn, annotations_dir, vocab_path, samples_path)
        assert n_studies == 1
        run3 = {r[0]: r[1:] for r in conn.execute(
            "SELECT tag, category, source FROM sample_tags WHERE sample_id = 'RUN3'").fetchall()}
        assert set(run3) == {"submerged", "glucose", "treated", "30C", "3h_post_treatment", "del_faaA"}
        assert run3["glucose"] == ("carbon_source", "sample_metadata")
        assert run3["del_faaA"][0] == "genotype"
        assert n_tags == 3 + 3 + 6
        assert conn.execute("SELECT paper_year FROM study_annotations").fetchone()[0] == 2020
        assert conn.execute("SELECT COUNT(*) FROM tag_vocabulary").fetchone()[0] == 4
    finally:
        conn.close()


def test_load_refuses_invalid_annotations(env, tmp_path):
    vocab_path, samples_path, annotations_dir = env
    _write(annotations_dir, _annotation(study_summary={"objective": "", "experimental_design": "d", "main_finding": "f"}))
    db_path = tmp_path / "t.duckdb"
    apply_migrations(db_path)
    conn = duckdb.connect(str(db_path))
    try:
        with pytest.raises(AnnotationValidationError):
            load_study_annotations(conn, annotations_dir, vocab_path, samples_path)
    finally:
        conn.close()


def test_deposition_snippets_separate_origin_from_reuse():
    origin = "Methods. The RNA-seq raw data have been deposited in DDBJ with the accession code BioProject PRJDB1."
    reuse = "We compared our results with a public time course (PRJDB1) reported by others."
    assert deposition_snippets(origin, ["PRJDB1"])[0]["deposition_statement"] is True
    assert deposition_snippets(reuse, ["PRJDB1"])[0]["deposition_statement"] is False


def test_committed_annotations_are_valid():
    """The real curated files must always pass validation against the real vocabulary/samples."""
    vocab = load_vocabulary(SAMPLE_TAG_VOCABULARY_FILE)
    samples = pd.read_csv(SAMPLES_CURATION_FILE, sep="\t", dtype=str, keep_default_na=False)
    paths = sorted(STUDY_ANNOTATIONS_DIR.glob("*.json"))
    assert paths, "no curated study annotations found"
    problems = [p for path in paths for p in validate_annotation(load_annotation(path), vocab, samples)]
    assert problems == []
