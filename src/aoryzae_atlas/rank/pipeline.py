"""End-to-end pan-transcriptomic expression rank: DuckDB -> per-gene table.

The single orchestration entry point shared by `atlas rank genes`, `atlas refresh` and the
consistency check at the end of notebooks/gene_expression_classification.ipynb. If the pipeline
changes (a new metric, a different flag rule, another threshold), change it HERE: the CLI and the
web export pick it up on the next `atlas refresh`, and the notebook's check cell fails until the
notebook is brought back in line -- so the two can never drift apart silently.

Unit of analysis: the biosample (runs of one biosample are averaged). No condition curation is needed.
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd

from ..matrix.build import collapse_to_biosamples, fetch_biosample_units, fetch_gene_sample_tpm
from .classes import (
    CLASS_ORDER,
    ClassParams,
    Thresholds,
    assign_classes,
    class_agreement,
    class_stability,
    derive_thresholds,
    level_tiers,
)
from .diagnostics import build_quality_flags, dominance_flag, group_dominance
from .metrics import compute_gene_metrics
from .scores import compute_scores

__all__ = [
    "RANK_PIPELINE_VERSION",
    "NoQuantifiedSamplesError",
    "ExpressionRankResult",
    "compute_flags",
    "assemble_rank_table",
    "leave_out_robustness",
    "build_expression_rank",
    "write_rank_outputs",
]

RANK_PIPELINE_VERSION = "1"
BORDERLINE_STABILITY_MAX = 0.75      # class changes under more than a quarter of the threshold perturbations
MIN_DETECTED_FOR_SUPPORT = 3         # non-silent class resting on < 3 samples at >= 1 TPM
MIN_SAMPLES_FOR_SUPPORT = 20         # atlas-wide: fewer independent samples than this -> every gene flagged
MIN_SAMPLES_FOR_ROBUSTNESS_RUN = 20  # skip a leave-out run that would leave fewer independent samples than this

SPEC_COLUMNS = [
    "median_TPM", "median_logTPM", "P10_TPM", "P25_TPM", "P75_TPM", "P90_TPM",
    "prevalence_TPM_0.1", "prevalence_TPM_1", "prevalence_TPM_5", "MAD_logTPM", "IQR_logTPM", "Tau",
    "max_TPM", "max_to_median_ratio", "P90_to_median_ratio",
    "expression_level_score", "expression_stability_score", "expression_specificity_score", "expression_prevalence_score",
    "expression_class", "global_expression_rank", "study_dominance", "quality_flags",
]


class NoQuantifiedSamplesError(Exception):
    """Raised when the database has no QUANTIFIED samples with expression rows yet."""


@dataclass
class ExpressionRankResult:
    final: pd.DataFrame
    """One row per gene (index `gene_id`): spec columns first, then extras."""
    thresholds: Thresholds
    params: ClassParams
    scope: dict
    robustness: pd.DataFrame = field(default_factory=pd.DataFrame)
    perturbation_summary: pd.DataFrame = field(default_factory=pd.DataFrame)
    tpm: pd.DataFrame = field(default_factory=pd.DataFrame)
    """(genes x independent biological samples) raw TPM, the pipeline's unit-of-analysis matrix."""


def compute_flags(
    metrics: pd.DataFrame,
    classes: pd.Series,
    class_stab: pd.Series,
    study_dom: pd.DataFrame,
    strain_dom: pd.DataFrame,
    multi_strain: bool,
) -> pd.DataFrame:
    """Boolean quality-flag table (never used to exclude a gene)."""
    study_flag = dominance_flag(study_dom)
    strain_flag = dominance_flag(strain_dom) if multi_strain else pd.Series(False, index=metrics.index)
    low_support = (
        ((metrics["n_detected_TPM_1"] < MIN_DETECTED_FOR_SUPPORT) & (classes.astype(str) != "Rare/Silent"))
        | (metrics["n_samples"] < MIN_SAMPLES_FOR_SUPPORT)
    )
    return pd.DataFrame(
        {
            "possible_study_effect": study_flag,
            "possible_strain_effect": strain_flag,
            "low_sample_support": low_support,
            "borderline_class": class_stab < BORDERLINE_STABILITY_MAX,
        }
    )


def assemble_rank_table(
    metrics: pd.DataFrame,
    scores: pd.DataFrame,
    classes: pd.Series,
    tiers: pd.Series,
    class_stab: pd.Series,
    study_dom: pd.DataFrame,
    strain_dom: pd.DataFrame,
    quality_flags: pd.Series,
    gene_annotations: pd.DataFrame | None = None,
) -> pd.DataFrame:
    final = metrics.join(scores).copy()
    final["expression_class"] = classes.astype(str)
    final["level_tier"] = tiers
    final["class_stability"] = class_stab
    final["study_dominance"] = study_dom["dominance"]
    final["dominant_study"] = study_dom["dominant_group"]
    final["study_dominance_q"] = study_dom["dominance_q"]
    final["strain_dominance"] = strain_dom["dominance"]
    final["dominant_strain"] = strain_dom["dominant_group"]
    final["quality_flags"] = quality_flags
    if gene_annotations is not None:
        final = final.join(gene_annotations[["gene_symbol", "description"]])
    final.index.name = "gene_id"
    return final[SPEC_COLUMNS + [c for c in final.columns if c not in SPEC_COLUMNS]]


def leave_out_robustness(
    tpm: pd.DataFrame, unit_meta: pd.DataFrame, base_classes: pd.Series, params: ClassParams
) -> pd.DataFrame:
    """Agreement of the classes re-derived (thresholds included) after removing one study / one strain at a time."""
    records = []

    def rerun(label: str, keep: pd.Series) -> None:
        cols = list(unit_meta.index[keep.to_numpy()])
        if len(cols) < MIN_SAMPLES_FOR_ROBUSTNESS_RUN or len(cols) == len(unit_meta):
            return
        classes = assign_classes(compute_gene_metrics(tpm[cols]), params)
        records.append({"perturbation": label, "n_samples_used": len(cols), "class_agreement": class_agreement(base_classes, classes)})

    for study in sorted(unit_meta["bioproject"].unique()):
        rerun(f"leave out study {study}", unit_meta["bioproject"] != study)
    if unit_meta["strain"].nunique() > 1:
        for strain in sorted(unit_meta["strain"].unique()):
            rerun(f"leave out strain {strain}", unit_meta["strain"] != strain)
    return pd.DataFrame(records, columns=["perturbation", "n_samples_used", "class_agreement"])


def build_expression_rank(
    conn: duckdb.DuckDBPyConnection,
    params: ClassParams = ClassParams(),
    with_robustness: bool = True,
) -> ExpressionRankResult:
    units = fetch_biosample_units(conn)
    if units.empty:
        raise NoQuantifiedSamplesError("no QUANTIFIED samples in the database yet")
    units["strain"] = units["strain"].fillna("unknown")
    long_df = fetch_gene_sample_tpm(conn)
    if long_df.empty:
        raise NoQuantifiedSamplesError("QUANTIFIED samples have no gene_expression rows")
    tpm = collapse_to_biosamples(long_df, units)

    unit_meta = units.drop_duplicates("unit_id").set_index("unit_id").reindex(tpm.columns)[["bioproject", "strain"]]
    genes_tbl = conn.execute("SELECT canonical_gene_id, gene_symbol, description FROM genes").fetchdf().set_index("canonical_gene_id")

    metrics = compute_gene_metrics(tpm)
    scores = compute_scores(metrics)
    thresholds = derive_thresholds(metrics, params)
    classes = assign_classes(metrics, params)
    tiers = level_tiers(metrics, params)
    class_stab, perturbation_summary = class_stability(metrics, params)
    study_dom = group_dominance(tpm, unit_meta["bioproject"])
    strain_dom = group_dominance(tpm, unit_meta["strain"])
    flags = compute_flags(metrics, classes, class_stab, study_dom, strain_dom, unit_meta["strain"].nunique() > 1)
    final = assemble_rank_table(
        metrics, scores, classes, tiers, class_stab, study_dom, strain_dom,
        build_quality_flags({c: flags[c] for c in flags.columns}), genes_tbl,
    )

    robustness = leave_out_robustness(tpm, unit_meta, classes, params) if with_robustness else pd.DataFrame()
    counts = classes.value_counts().reindex(CLASS_ORDER).fillna(0).astype(int)
    scope = {
        "pipeline_version": RANK_PIPELINE_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "n_genes": int(len(final)),
        "n_runs": int(units["sample_id"].nunique()),
        "n_samples": int(tpm.shape[1]),
        "n_studies": int(unit_meta["bioproject"].nunique()),
        "n_strains": int(unit_meta["strain"].nunique()),
        "samples_per_study": {k: int(v) for k, v in unit_meta["bioproject"].value_counts().items()},
        "samples_per_strain": {k: int(v) for k, v in unit_meta["strain"].value_counts().items()},
        "class_order": list(CLASS_ORDER),
        "class_counts": {k: int(v) for k, v in counts.items()},
        "flag_rates": {c: float(flags[c].mean()) for c in flags.columns},
        "thresholds": {k: (v if isinstance(v, (int, float)) else float(v)) for k, v in asdict(thresholds).items()},
        "params": {k: (list(v) if isinstance(v, tuple) else v) for k, v in asdict(params).items()},
        "robustness": robustness.to_dict(orient="records"),
        "median_robustness_agreement": float(robustness["class_agreement"].median()) if len(robustness) else None,
    }
    return ExpressionRankResult(
        final=final, thresholds=thresholds, params=params, scope=scope,
        robustness=robustness, perturbation_summary=perturbation_summary, tpm=tpm,
    )


def write_rank_outputs(
    result: ExpressionRankResult,
    parquet_path: Path,
    tsv_gz_path: Path,
    thresholds_path: Path,
    summary_path: Path,
    biosample_matrix_path: Path | None = None,
) -> None:
    """Persist the per-gene table, derived thresholds, scope/robustness summary and (optionally) the unit matrix."""
    for path in (parquet_path, tsv_gz_path, thresholds_path, summary_path):
        path.parent.mkdir(parents=True, exist_ok=True)
    table = result.final.reset_index()
    table.to_parquet(parquet_path, index=False)
    table.to_csv(tsv_gz_path, sep="\t", index=False, compression="gzip")
    result.thresholds.as_frame().to_csv(thresholds_path, sep="\t", index=False)
    summary_path.write_text(json.dumps(_clean(result.scope), indent=2, allow_nan=False), encoding="utf-8")
    if biosample_matrix_path is not None:
        biosample_matrix_path.parent.mkdir(parents=True, exist_ok=True)
        result.tpm.to_parquet(biosample_matrix_path)


def _clean(value):
    """Recursively make a structure strict-JSON safe: numpy scalars -> python, NaN/inf -> None."""
    if isinstance(value, dict):
        return {k: _clean(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_clean(v) for v in value]
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, (float, np.floating)):
        return None if not np.isfinite(value) else float(value)
    return value
