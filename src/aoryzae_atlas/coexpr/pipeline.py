"""End-to-end gene co-expression network: DuckDB -> neighbour lists, enrichment, benchmark.

The single orchestration entry point shared by `atlas coexpr build`, `atlas refresh` and
notebooks/coexpression_network.ipynb (whose last cell checks itself against this function). Change the
workflow HERE (a different filter, a new edge-support column, another mode) and everything downstream
picks it up on the next `atlas refresh`.

Unit of analysis: the biosample. A biosample enters when its summed assigned reads reach
`params.min_assigned_reads` (AFED: >= 10M mapped reads). Two modes are built on the same genes:
`all_samples` (AFED-style, no correction) and `within_study` (per-study centering).
"""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd

from ..matrix.build import collapse_to_biosamples, fetch_biosample_depth, fetch_biosample_units, fetch_gene_sample_tpm
from ..rank.pipeline import _clean
from ..rank.validation import build_gene_sets, load_go_annotations
from .enrichment import build_custom_term_sets, build_term_sets, load_go_obo, neighbourhood_enrichment
from .network import (
    MODES,
    PreparedExpression,
    CoexprParams,
    correlation_null,
    depth_scope_table,
    functional_benchmark,
    neighbour_table,
    null_summary,
    prepare_expression,
    samples_for_mode,
    select_biosamples,
    study_consistency,
    top_neighbours,
)

__all__ = [
    "COEXPR_PIPELINE_VERSION",
    "CoexpressionNotPossibleError",
    "CoexprModeResult",
    "CoexpressionResult",
    "build_coexpression",
    "write_coexpression_outputs",
]

COEXPR_PIPELINE_VERSION = "1"
ENRICHMENT_ALPHA = 0.05
MIN_TERM_SIZE = 5
MAX_TERM_SIZE = 500


class CoexpressionNotPossibleError(Exception):
    """No quantified data, or too few biosamples pass the depth filter for a meaningful network."""


@dataclass
class CoexprModeResult:
    mode: str
    prepared: PreparedExpression
    neighbours: pd.DataFrame
    benchmark: pd.DataFrame
    null: dict
    enrichment: pd.DataFrame = field(default_factory=pd.DataFrame)
    set_enrichment: pd.DataFrame = field(default_factory=pd.DataFrame)
    """Enrichment of each neighbourhood in the curated gene sets (secretome...), kept apart from GO on purpose."""


@dataclass
class CoexpressionResult:
    params: CoexprParams
    scope: dict
    modes: dict[str, CoexprModeResult]
    depth: pd.Series
    """Assigned reads per biosample (all biosamples, selected or not)."""
    unit_meta: pd.DataFrame
    """bioproject / strain per biosample."""

    def neighbours(self) -> pd.DataFrame:
        return pd.concat([m.neighbours.assign(mode=m.mode) for m in self.modes.values()], ignore_index=True)

    def benchmark(self) -> pd.DataFrame:
        return pd.concat([m.benchmark.assign(mode=m.mode) for m in self.modes.values()], ignore_index=True)

    def enrichment(self) -> pd.DataFrame:
        frames = [m.enrichment.assign(mode=m.mode) for m in self.modes.values() if len(m.enrichment)]
        return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()

    def set_enrichment(self) -> pd.DataFrame:
        frames = [m.set_enrichment.assign(mode=m.mode) for m in self.modes.values() if len(m.set_enrichment)]
        return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def _load_go(gaf_path: Path | None) -> pd.DataFrame:
    if gaf_path is not None and Path(gaf_path).is_file():
        return load_go_annotations(gaf_path)
    return pd.DataFrame(columns=["gene", "go_id"])


def build_coexpression(
    conn: duckdb.DuckDBPyConnection,
    params: CoexprParams = CoexprParams(),
    gaf_path: Path | None = None,
    obo_path: Path | None = None,
    with_enrichment: bool = True,
    curated_sets: dict[str, list[str]] | None = None,
) -> CoexpressionResult:
    units = fetch_biosample_units(conn)
    if units.empty:
        raise CoexpressionNotPossibleError("no QUANTIFIED samples in the database yet")
    units["strain"] = units["strain"].fillna("unknown")
    long_df = fetch_gene_sample_tpm(conn)
    if long_df.empty:
        raise CoexpressionNotPossibleError("QUANTIFIED samples have no gene_expression rows")
    tpm_all = collapse_to_biosamples(long_df, units)
    unit_meta = units.drop_duplicates("unit_id").set_index("unit_id").reindex(tpm_all.columns)[["bioproject", "strain"]]
    depth = fetch_biosample_depth(conn, units).reindex(tpm_all.columns)

    selected = select_biosamples(depth, params.min_assigned_reads)
    if len(selected) < params.min_samples:
        raise CoexpressionNotPossibleError(
            f"only {len(selected)} biosample(s) reach {params.min_assigned_reads / 1e6:g}M assigned reads "
            f"(need >= {params.min_samples}); lower --min-reads-millions or add deeper samples"
        )
    tpm = tpm_all[selected]
    genes = tpm.index[(tpm.mean(axis=1) >= params.min_mean_tpm).to_numpy()]
    study_of = unit_meta.loc[selected, "bioproject"]

    genes_tbl = conn.execute("SELECT canonical_gene_id, description FROM genes").fetchdf().set_index("canonical_gene_id")
    gene_sets = build_gene_sets(_load_go(gaf_path), genes_tbl["description"], genes)

    term_sets, go_scope = None, None
    if with_enrichment:
        go = _load_go(gaf_path)
        if len(go):
            onto = load_go_obo(obo_path) if obo_path is not None and Path(obo_path).is_file() else None
            term_sets = build_term_sets(go, genes, onto, MIN_TERM_SIZE, MAX_TERM_SIZE)
            go_scope = {
                "source": term_sets.source, "n_terms": int(len(term_sets.terms)), "n_annotated_genes": int(term_sets.n_genes),
                "min_term_size": MIN_TERM_SIZE, "max_term_size": MAX_TERM_SIZE, "alpha": ENRICHMENT_ALPHA,
            }

    set_term_sets, set_scope = None, None
    if with_enrichment and curated_sets:
        set_term_sets = build_custom_term_sets(curated_sets, genes)
        set_scope = {name.removeprefix("SET:"): {"n_in_network": int(n)} for name, n in zip(set_term_sets.terms, set_term_sets.sizes)}

    modes: dict[str, CoexprModeResult] = {}
    mode_scope: dict[str, dict] = {}
    skipped: dict[str, str] = {}
    for mode_index, mode in enumerate(MODES):
        n_usable = len(samples_for_mode(study_of, mode, params))
        if n_usable < params.min_samples:
            skipped[mode] = f"only {n_usable} biosample(s) left after the per-study filter (need >= {params.min_samples})"
            continue
        prepared = prepare_expression(tpm, study_of, mode, params, genes=genes)
        null = correlation_null(prepared.z, params.null_pairs, params.seed + mode_index)
        nb = top_neighbours(prepared.z, params.top_n)
        table = neighbour_table(prepared.genes, nb, null)
        top_n = nb.idx.shape[1]
        support, n_tested = study_consistency(
            prepared, np.repeat(np.arange(len(prepared.genes)), top_n), nb.idx.ravel(), params
        )
        table["within_study_median_r"] = support
        table["n_studies_tested"] = n_tested
        benchmark = functional_benchmark(prepared.z, prepared.genes, gene_sets, null, seed=params.seed + mode_index)
        enrichment = (
            neighbourhood_enrichment(table, term_sets, alpha=ENRICHMENT_ALPHA) if term_sets is not None else pd.DataFrame()
        )
        set_enrichment = (
            neighbourhood_enrichment(table, set_term_sets, alpha=ENRICHMENT_ALPHA) if set_term_sets is not None else pd.DataFrame()
        )
        modes[mode] = CoexprModeResult(mode, prepared, table, benchmark, null_summary(null), enrichment, set_enrichment)
        mode_scope[mode] = {
            "n_biosamples": prepared.n_samples,
            "n_studies": prepared.n_studies,
            "n_genes": int(len(prepared.genes)),
            "top_n": int(top_n),
            "null": modes[mode].null,
            "benchmark": benchmark.to_dict(orient="records"),
            "median_top1_r": float(np.median(nb.r[:, 0])),
            "median_top_n_r": float(np.median(nb.r[:, -1])),
            "n_genes_with_enrichment": int(enrichment["gene_id"].nunique()) if len(enrichment) else 0,
            "n_genes_with_gene_set_enrichment": int(set_enrichment["gene_id"].nunique()) if len(set_enrichment) else 0,
        }
    if not modes:
        raise CoexpressionNotPossibleError("; ".join(f"{m}: {why}" for m, why in skipped.items()))

    scope = {
        "pipeline_version": COEXPR_PIPELINE_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "params": asdict(params),
        "n_biosamples_total": int(tpm_all.shape[1]),
        "n_biosamples_unknown_depth": int(depth.isna().sum()),
        "n_biosamples_selected": int(len(selected)),
        "n_studies_selected": int(study_of.nunique()),
        "n_strains_selected": int(unit_meta.loc[selected, "strain"].nunique()),
        "median_assigned_reads_selected": float(depth.loc[selected].median()),
        "depth_table": depth_scope_table(depth, unit_meta).to_dict(orient="records"),
        "n_genes": int(len(genes)),
        "modes": mode_scope,
        "skipped_modes": skipped,
        "go": go_scope,
        "gene_sets": set_scope,
    }
    return CoexpressionResult(params=params, scope=scope, modes=modes, depth=depth, unit_meta=unit_meta)


def write_coexpression_outputs(
    result: CoexpressionResult,
    neighbours_path: Path,
    enrichment_path: Path,
    benchmark_path: Path,
    summary_path: Path,
    profiles_dir: Path | None = None,
    set_enrichment_path: Path | None = None,
) -> None:
    """Persist neighbour lists, enrichment (when GO was available), the benchmark, the run summary and the profiles."""
    for path in (neighbours_path, enrichment_path, benchmark_path, summary_path):
        path.parent.mkdir(parents=True, exist_ok=True)
    result.neighbours().to_parquet(neighbours_path, index=False)
    enrichment = result.enrichment()
    if len(enrichment):
        enrichment.to_parquet(enrichment_path, index=False)
    elif enrichment_path.exists():
        enrichment_path.unlink()          # a stale table from an earlier run with GO must not outlive a run without
    if set_enrichment_path is not None:
        set_enrichment_path.parent.mkdir(parents=True, exist_ok=True)
        set_table = result.set_enrichment()
        if len(set_table):
            set_table.to_parquet(set_enrichment_path, index=False)
        elif set_enrichment_path.exists():
            set_enrichment_path.unlink()
    result.benchmark().to_csv(benchmark_path, sep="\t", index=False)
    summary_path.write_text(json.dumps(_clean(result.scope), indent=2, allow_nan=False), encoding="utf-8")
    if profiles_dir is not None:
        profiles_dir.mkdir(parents=True, exist_ok=True)
        for mode, m in result.modes.items():
            pd.DataFrame(m.prepared.z, index=m.prepared.genes, columns=m.prepared.samples).to_parquet(profiles_dir / f"zscores_{mode}.parquet")
