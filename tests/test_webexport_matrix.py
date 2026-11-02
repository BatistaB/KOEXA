"""write_expression_matrix: dense float32 gene x sample binaries the web app reads as typed arrays."""
from __future__ import annotations

import json

import duckdb
import numpy as np

from aoryzae_atlas.webexport.build import write_expression_matrix


def _conn():
    conn = duckdb.connect(":memory:")
    conn.execute("CREATE TABLE samples (sample_id VARCHAR, pipeline_status VARCHAR, condition_id VARCHAR)")
    conn.execute("CREATE TABLE gene_expression (sample_id VARCHAR, canonical_gene_id VARCHAR, TPM DOUBLE, estimated_counts DOUBLE)")
    conn.execute("INSERT INTO samples VALUES ('S1','QUANTIFIED','c1'),('S2','QUANTIFIED','c1'),('S3','QUANTIFIED',NULL),('S4','APPROVED','c1')")
    conn.execute(
        "INSERT INTO gene_expression VALUES ('S1','G2',5,50),('S2','G2',7.5,75),('S1','G1',1,10),"
        "('S3','G1',99,990),('S4','G1',99,990)"
    )
    return conn


def test_matrix_layout_and_filtering(tmp_path):
    info = write_expression_matrix(_conn(), tmp_path)
    index = json.loads((tmp_path / "expression_index.json").read_text())
    assert index == {"genes": ["G1", "G2"], "samples": ["S1", "S2"]}  # uncurated / non-QUANTIFIED samples excluded
    tpm = np.frombuffer((tmp_path / "expression_tpm.bin").read_bytes(), dtype="<f4").reshape(2, 2)
    counts = np.frombuffer((tmp_path / "expression_counts.bin").read_bytes(), dtype="<f4").reshape(2, 2)
    assert tpm.tolist() == [[1.0, 0.0], [5.0, 7.5]]  # missing (G1, S2) is 0, rows follow `genes`
    assert counts[1].tolist() == [50.0, 75.0]
    assert info["n_genes"] == 2 and info["n_samples"] == 2


def test_removes_stale_json(tmp_path):
    (tmp_path / "expression.json").write_text("{}")
    write_expression_matrix(_conn(), tmp_path)
    assert not (tmp_path / "expression.json").exists()
