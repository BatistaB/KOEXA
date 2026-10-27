"""Gene co-expression network: sample selection, correlation, neighbour lists, edge support, benchmark.

Design (see docs/decisions/0008-coexpression-network.md). AFED builds its network from samples with
>= 10M mapped reads, genes with mean TPM >= 1 and Pearson r >= 0.5, with no batch correction. Our atlas
is far more heterogeneous (many studies/strains), so the same recipe is kept as the `all_samples` mode and
complemented by a `within_study` mode (per-study centering of every gene, so a correlation cannot come from
between-study offsets). Neighbours are ranked lists (top-N, mutual rank), not a fixed |r| cut-off, because
the fraction of *random* gene pairs passing a fixed cut-off depends on how structured the atlas is.

Unit of analysis = biosample (runs of one biosample are averaged upstream); expression = log2(TPM + 1).
Everything here is a pure function of arrays/frames so it is unit-testable without a database.
"""
from __future__ import annotations

import warnings
from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy.stats import rankdata

__all__ = [
    "MODES",
    "METHODS",
    "CoexprParams",
    "PreparedExpression",
    "Neighbours",
    "select_biosamples",
    "depth_scope_table",
    "samples_for_mode",
    "prepare_expression",
    "correlation_null",
    "null_summary",
    "top_neighbours",
    "neighbour_table",
    "select_edges",
    "study_consistency",
    "functional_benchmark",
    "coexpressed_with_set",
]

MODES = ("all_samples", "within_study")
METHODS = ("pearson", "spearman")
MAX_GENES = np.iinfo(np.uint16).max      # ranks are stored as uint16 (a genome has ~12k genes)


@dataclass(frozen=True)
class CoexprParams:
    min_assigned_reads: float = 10_000_000.0
    """A biosample enters the network only if the summed `salmon_total_gene_assigned_counts` of its runs reaches this (AFED: 10M)."""
    min_mean_tpm: float = 1.0
    """Genes need a mean TPM >= this over the selected biosamples (AFED: 1). Same gene universe in every mode."""
    method: str = "spearman"
    top_n: int = 50
    min_samples: int = 20
    """Fewer selected biosamples than this and no network is built (correlations from a handful of points are noise)."""
    min_samples_per_study: int = 3
    """within_study centering / per-study support need >= this many biosamples in a study; smaller studies are left out of that mode."""
    null_pairs: int = 200_000
    seed: int = 0

    def __post_init__(self) -> None:
        if self.method not in METHODS:
            raise ValueError(f"method must be one of {METHODS}, got {self.method!r}")
        if self.top_n < 1 or self.min_samples < 3 or self.min_samples_per_study < 3:
            raise ValueError("top_n >= 1, min_samples >= 3 and min_samples_per_study >= 3 are required")


@dataclass
class PreparedExpression:
    mode: str
    genes: pd.Index
    samples: pd.Index
    log_expr: np.ndarray
    """(genes x samples) log2(TPM+1) before any centering/ranking, float32."""
    z: np.ndarray
    """(genes x samples) standardized profiles (row mean 0, row std 1, zero-variance rows all 0): r = z @ z.T / n_samples."""
    study_of: pd.Series
    """bioproject of each sample (index = samples)."""

    @property
    def n_samples(self) -> int:
        return len(self.samples)

    @property
    def n_studies(self) -> int:
        return int(self.study_of.nunique())


@dataclass
class Neighbours:
    idx: np.ndarray            # (G, top_n) int32, neighbour gene index, best first
    r: np.ndarray              # (G, top_n) float32
    reverse_rank: np.ndarray   # (G, top_n) int32, rank of the gene in the NEIGHBOUR's own list


# --- sample selection -------------------------------------------------------------------------------------

def select_biosamples(depth: pd.Series, min_assigned_reads: float) -> pd.Index:
    """Biosamples whose summed assigned reads reach the cut-off. Unknown depth (NaN) never passes a positive cut-off."""
    if min_assigned_reads <= 0:
        return depth.index
    return depth.index[(depth >= min_assigned_reads).to_numpy()]


def depth_scope_table(depth: pd.Series, unit_meta: pd.DataFrame, cutoffs_millions=(0, 5, 10, 20, 30)) -> pd.DataFrame:
    """How many biosamples / studies / strains survive each read-depth cut-off (the data behind choosing `min_assigned_reads`)."""
    rows = []
    for cut in cutoffs_millions:
        kept = select_biosamples(depth, cut * 1e6)
        meta = unit_meta.loc[kept]
        rows.append({
            "min_assigned_reads_M": cut, "biosamples": len(kept),
            "studies": int(meta["bioproject"].nunique()), "strains": int(meta["strain"].nunique()),
        })
    return pd.DataFrame(rows)


# --- matrix preparation -----------------------------------------------------------------------------------

def _standardize(x: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Row z-scores (population SD); zero-variance rows become all-zero. Returns (z float32, has_variance)."""
    centered = x - x.mean(axis=1, keepdims=True)
    sd = centered.std(axis=1, keepdims=True)
    has_variance = sd[:, 0] > 1e-12
    z = np.divide(centered, sd, out=np.zeros_like(centered), where=sd > 1e-12)
    return z.astype(np.float32), has_variance


def samples_for_mode(study_of: pd.Series, mode: str, params: CoexprParams) -> pd.Index:
    """Biosamples a mode can use: all of them, or (within_study) only those from studies with enough biosamples to be centered."""
    if mode != "within_study":
        return study_of.index
    counts = study_of.value_counts()
    return study_of.index[(study_of.map(counts) >= params.min_samples_per_study).to_numpy()]


def prepare_expression(
    tpm: pd.DataFrame, study_of: pd.Series, mode: str, params: CoexprParams, genes: pd.Index | None = None
) -> PreparedExpression:
    """Profiles for one mode from a (genes x selected biosamples) TPM frame.

    `genes` fixes the gene universe (default: mean TPM >= params.min_mean_tpm over `tpm`), so every mode
    of one run is built on the same genes. `within_study` additionally drops studies with fewer than
    `params.min_samples_per_study` biosamples (they cannot be centered) and subtracts each gene's
    per-study mean of log2(TPM+1). With method='spearman' the (centered) values are then ranked.
    """
    if mode not in MODES:
        raise ValueError(f"mode must be one of {MODES}, got {mode!r}")
    if genes is None:
        genes = tpm.index[(tpm.mean(axis=1) >= params.min_mean_tpm).to_numpy()]
    study_of = study_of.reindex(tpm.columns)
    usable = samples_for_mode(study_of, mode, params)
    tpm, study_of = tpm[usable], study_of[usable]
    log_expr = np.log2(tpm.loc[genes].to_numpy(dtype=np.float64) + 1.0)
    x = log_expr.copy()
    if mode == "within_study":
        groups = study_of.to_numpy()
        for study in np.unique(groups):
            cols = groups == study
            x[:, cols] -= x[:, cols].mean(axis=1, keepdims=True)
    if params.method == "spearman":
        x = rankdata(x, axis=1)
    z, _ = _standardize(x)
    return PreparedExpression(mode, genes, tpm.columns, log_expr.astype(np.float32), z, study_of)


# --- correlations -----------------------------------------------------------------------------------------

def _pair_r(z: np.ndarray, i: np.ndarray, j: np.ndarray) -> np.ndarray:
    return np.einsum("ij,ij->i", z[i], z[j]) / z.shape[1]


def correlation_null(z: np.ndarray, n_pairs: int, seed: int) -> np.ndarray:
    """Sorted r of random distinct gene pairs: the background any observed r is judged against."""
    rng = np.random.default_rng(seed)
    g = z.shape[0]
    i = rng.integers(0, g, n_pairs)
    j = rng.integers(0, g, n_pairs)
    keep = i != j
    return np.sort(_pair_r(z, i[keep], j[keep]))


def null_summary(null: np.ndarray) -> dict:
    """Plain-number description of the background r distribution (written to the summary JSON)."""
    return {
        "n_pairs": int(len(null)),
        "mean_r": float(null.mean()),
        "q50_r": float(np.quantile(null, 0.50)),
        "q99_r": float(np.quantile(null, 0.99)),
        "fraction_abs_r_ge_0.5": float((np.abs(null) >= 0.5).mean()),
        "fraction_r_ge_0.5": float((null >= 0.5).mean()),
    }


def top_neighbours(z: np.ndarray, top_n: int, block_size: int = 1024) -> Neighbours:
    """Top-N most correlated genes per gene, with the reverse rank needed for mutual rank.

    Computed block-wise (never the full float matrix at once); the rank matrix is kept as uint16, so this
    needs ~2 bytes x G^2 (about 0.3 GB for 12k genes). Self-correlation is excluded.
    """
    g, n = z.shape
    if g > MAX_GENES:
        raise ValueError(f"{g} genes exceeds the uint16 rank limit ({MAX_GENES})")
    top_n = min(top_n, g - 1)
    z32 = np.ascontiguousarray(z, dtype=np.float32)
    ranks = np.empty((g, g), dtype=np.uint16)
    idx = np.empty((g, top_n), dtype=np.int32)
    r_top = np.empty((g, top_n), dtype=np.float32)
    positions = np.arange(1, g + 1, dtype=np.uint16)
    for start in range(0, g, block_size):
        stop = min(start + block_size, g)
        r = z32[start:stop] @ z32.T / n
        np.clip(r, -1.0, 1.0, out=r)
        rows = np.arange(stop - start)
        r[rows, np.arange(start, stop)] = -np.inf          # self sorts last
        order = np.argsort(-r, axis=1, kind="stable")
        ranks[start:stop][rows[:, None], order] = positions
        idx[start:stop] = order[:, :top_n]
        r_top[start:stop] = r[rows[:, None], order[:, :top_n]]
    reverse_rank = ranks[idx, np.arange(g)[:, None]].astype(np.int32)
    return Neighbours(idx=idx, r=r_top, reverse_rank=reverse_rank)


def neighbour_table(genes: pd.Index, nb: Neighbours, null: np.ndarray) -> pd.DataFrame:
    """Directed edges gene -> neighbour (best first) with rank, r, mutual rank and the background tail of r.

    `mutual_rank` = sqrt(rank(j in i's list) * rank(i in j's list)) (Obayashi & Kinoshita, ATTED-II): low only
    when the relationship is close from BOTH sides, which tames hub genes that are everybody's neighbour.
    `bg_tail` = fraction of random gene pairs with r at least this large (0 = beyond every sampled pair). The
    random-pair background is wide in a structured atlas (its upper percentiles can exceed the r of a gene's
    lower-ranked neighbours), so `bg_tail` and `r` say little on their own -- rank, mutual rank and
    `within_study_median_r` are the criteria to cut edges on.
    """
    g, top_n = nb.idx.shape
    rank = np.tile(np.arange(1, top_n + 1, dtype=np.int32), g)
    reverse = nb.reverse_rank.ravel()
    r = nb.r.ravel()
    bg_tail = 1.0 - np.searchsorted(null, r, side="left") / len(null)
    gene_ids = genes.to_numpy()
    return pd.DataFrame(
        {
            "gene_id": np.repeat(gene_ids, top_n),
            "neighbour_id": gene_ids[nb.idx.ravel()],
            "rank": rank,
            "r": r,
            "reverse_rank": reverse,
            "mutual_rank": np.sqrt(rank.astype(np.float64) * reverse).astype(np.float32),
            "bg_tail": bg_tail.astype(np.float32),
        }
    )


def select_edges(table: pd.DataFrame, max_mutual_rank: float, min_within_study_r: float | None = None) -> pd.DataFrame:
    """Undirected network edges from a neighbour table: mutual rank <= cut (and, optionally, within-study support >= cut).

    A pair listed from both sides counts once. Columns: a, b (sorted ids), r, mutual_rank and, when present,
    within_study_median_r. Mutual rank is the sensible primary knob: it grows from 1 (each other's best
    neighbour) and, in a typical atlas, the graph stays modular at small values and merges into one giant
    component once the cut passes a few -- see notebooks/coexpression_network.ipynb section 9.
    """
    keep = table["mutual_rank"] <= max_mutual_rank
    if min_within_study_r is not None:
        keep &= table["within_study_median_r"] >= min_within_study_r
    d = table[keep]
    first = d["gene_id"].to_numpy() < d["neighbour_id"].to_numpy()
    edges = pd.DataFrame(
        {
            "a": np.where(first, d["gene_id"], d["neighbour_id"]),
            "b": np.where(first, d["neighbour_id"], d["gene_id"]),
            "r": d["r"].to_numpy(),
            "mutual_rank": d["mutual_rank"].to_numpy(),
        }
    )
    if "within_study_median_r" in d.columns:
        edges["within_study_median_r"] = d["within_study_median_r"].to_numpy()
    return edges.drop_duplicates(["a", "b"]).reset_index(drop=True)


def study_consistency(
    prepared: PreparedExpression, gene_idx: np.ndarray, neighbour_idx: np.ndarray, params: CoexprParams, chunk: int = 200_000
) -> tuple[np.ndarray, np.ndarray]:
    """Per edge: median over studies of the correlation computed INSIDE each study, and how many studies could be tested.

    A pair that correlates in the pooled data only because two studies differ in both genes shows a
    within-study median near 0; a real co-regulation shows up inside the individual studies too.
    Studies with fewer than `min_samples_per_study` biosamples, or where either gene is constant, do not vote.
    """
    counts = prepared.study_of.value_counts()
    studies = [s for s, c in counts.items() if c >= params.min_samples_per_study]
    n_edges = len(gene_idx)
    per_study = np.full((n_edges, max(len(studies), 1)), np.nan, dtype=np.float32)
    groups = prepared.study_of.to_numpy()
    for k, study in enumerate(studies):
        x = prepared.log_expr[:, groups == study].astype(np.float64)
        if params.method == "spearman":
            x = rankdata(x, axis=1)
        z, has_variance = _standardize(x)
        n_s = z.shape[1]
        for start in range(0, n_edges, chunk):
            sl = slice(start, start + chunk)
            i, j = gene_idx[sl], neighbour_idx[sl]
            r = np.einsum("ij,ij->i", z[i], z[j]) / n_s
            r[~(has_variance[i] & has_variance[j])] = np.nan
            per_study[sl, k] = r
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", category=RuntimeWarning)   # all-NaN rows -> NaN median
        median = np.nanmedian(per_study, axis=1)
    return median.astype(np.float32), (~np.isnan(per_study)).sum(axis=1).astype(np.int16)


# --- benchmark & set queries ------------------------------------------------------------------------------

def functional_benchmark(
    z: np.ndarray, genes: pd.Index, gene_sets: pd.DataFrame, null: np.ndarray, n_pairs: int = 30_000, seed: int = 0,
    min_genes: int = 10,
) -> pd.DataFrame:
    """Do genes of the same functional group correlate more than random gene pairs?

    AUC = P(r of a random same-group pair > r of a random gene pair); 0.5 = no signal. This is a sanity
    monitor for choosing/validating the workflow (AFED evaluated workflows the same way, by GO enrichment
    of the top-correlated genes), not a proof of biological accuracy: the groups are crude GO/keyword sets.
    """
    rng = np.random.default_rng(seed)
    position = {g: k for k, g in enumerate(genes)}
    records = []
    for group in gene_sets.columns:
        members = np.array([position[g] for g in gene_sets.index[gene_sets[group].to_numpy()] if g in position])
        if len(members) < min_genes:
            continue
        a, b = rng.choice(members, n_pairs), rng.choice(members, n_pairs)
        keep = a != b
        r = _pair_r(z, a[keep], b[keep])
        lo, hi = np.searchsorted(null, r, side="left"), np.searchsorted(null, r, side="right")
        auc = float(((lo + hi) / 2 / len(null)).mean())
        records.append({"group": group, "n_genes": int(len(members)), "n_pairs": int(keep.sum()), "auc": auc, "median_r": float(np.median(r))})
    return pd.DataFrame(records, columns=["group", "n_genes", "n_pairs", "auc", "median_r"])


def coexpressed_with_set(z: np.ndarray, genes: pd.Index, members: list[str], top_n: int = 50) -> pd.DataFrame:
    """Genes most correlated with a gene SET: ranked by the mean r to the members (a single gene works too).

    `min_r` is the weakest member correlation, so a gene tied to only one member of the set is visible as such.
    Members are not returned. Unknown members raise KeyError.
    """
    position = {g: k for k, g in enumerate(genes)}
    missing = [m for m in members if m not in position]
    if missing:
        raise KeyError(f"genes not in the network: {missing}")
    rows = np.array([position[m] for m in members])
    r = z @ z[rows].T / z.shape[1]                       # (G, n_members)
    mean_r, min_r = r.mean(axis=1), r.min(axis=1)
    mean_r[rows] = -np.inf
    order = np.argsort(-mean_r, kind="stable")[: min(top_n, len(genes) - len(rows))]
    return pd.DataFrame(
        {"gene_id": genes[order], "rank": np.arange(1, len(order) + 1), "mean_r": mean_r[order], "min_r": min_r[order]}
    )
