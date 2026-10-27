"""Functional enrichment of co-expressed genes (hypergeometric / one-sided Fisher, Benjamini-Hochberg).

Gene sets are GO terms from the FungiDB GAF. Without the ontology file only the *direct* annotations are
available and terms are identified by their GO id; with `go-basic.obo` annotations are propagated to
ancestors (is_a / part_of) and terms get names. The test universe is the set of annotated network genes:
an unannotated neighbour carries no information about any term, so it is neither a hit nor a miss.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import sparse
from scipy.stats import hypergeom

__all__ = [
    "GoOntology",
    "TermSets",
    "load_go_obo",
    "propagate_annotations",
    "build_term_sets",
    "build_custom_term_sets",
    "bh_adjust",
    "enrich_gene_set",
    "neighbourhood_enrichment",
]

PROPAGATE_RELATIONSHIPS = ("is_a", "part_of")


@dataclass
class GoOntology:
    names: dict[str, str] = field(default_factory=dict)
    namespaces: dict[str, str] = field(default_factory=dict)
    parents: dict[str, set[str]] = field(default_factory=dict)
    alt_ids: dict[str, str] = field(default_factory=dict)
    obsolete: set[str] = field(default_factory=set)


def load_go_obo(path: Path) -> GoOntology:
    """Parse the [Term] stanzas of a go-basic.obo: id, name, namespace, alt_id, is_a, relationship: part_of, is_obsolete."""
    onto = GoOntology()
    current: str | None = None
    in_term = False
    with Path(path).open(encoding="utf-8") as fh:
        for raw in fh:
            line = raw.strip()
            if line.startswith("["):
                in_term = line == "[Term]"
                current = None
                continue
            if not in_term or not line or ":" not in line:
                continue
            key, _, value = line.partition(": ")
            if key == "id":
                current = value
                onto.parents.setdefault(current, set())
            elif current is None:
                continue
            elif key == "name":
                onto.names[current] = value
            elif key == "namespace":
                onto.namespaces[current] = value
            elif key == "alt_id":
                onto.alt_ids[value] = current
            elif key == "is_obsolete" and value.strip() == "true":
                onto.obsolete.add(current)
            elif key == "is_a":
                onto.parents[current].add(value.split(" ! ")[0].strip())
            elif key == "relationship":
                parts = value.split()
                if len(parts) >= 2 and parts[0] in PROPAGATE_RELATIONSHIPS:
                    onto.parents[current].add(parts[1])
    return onto


def _ancestors(onto: GoOntology, term: str, cache: dict[str, frozenset[str]]) -> frozenset[str]:
    if term in cache:
        return cache[term]
    result: set[str] = {term}
    stack = list(onto.parents.get(term, ()))
    while stack:
        parent = stack.pop()
        if parent in result:
            continue
        result.add(parent)
        stack.extend(onto.parents.get(parent, ()))
    cache[term] = frozenset(result)
    return cache[term]


def propagate_annotations(go: pd.DataFrame, onto: GoOntology) -> pd.DataFrame:
    """(gene, go_id) expanded with every ancestor of each annotated term; alt ids are mapped, obsolete terms dropped."""
    go = go.assign(go_id=go["go_id"].map(lambda t: onto.alt_ids.get(t, t)))
    go = go[~go["go_id"].isin(onto.obsolete)]
    cache: dict[str, frozenset[str]] = {}
    expanded = {term: _ancestors(onto, term, cache) for term in go["go_id"].unique()}
    rows = [(gene, anc) for gene, term in zip(go["gene"], go["go_id"]) for anc in expanded[term]]
    return pd.DataFrame(rows, columns=["gene", "go_id"]).drop_duplicates()


@dataclass
class TermSets:
    genes: pd.Index
    """Annotated genes in the network = the universe every test is run against."""
    terms: pd.Index
    matrix: sparse.csr_matrix
    """(genes x terms) 0/1 membership."""
    names: pd.Series
    sizes: np.ndarray
    source: str = "direct GO annotations"

    @property
    def n_genes(self) -> int:
        return len(self.genes)


def build_term_sets(
    go: pd.DataFrame, network_genes: pd.Index, onto: GoOntology | None = None, min_size: int = 5, max_size: int = 500
) -> TermSets:
    """GO term x gene membership restricted to network genes; terms outside [min_size, max_size] genes are dropped.

    Very large terms ('metabolic process') are significant for almost any neighbourhood and say nothing, very
    small ones cannot reach significance; both bounds are parameters, recorded by the caller in the run summary.
    """
    source = "direct GO annotations (no ontology file: no propagation, no term names)"
    if onto is not None:
        go = propagate_annotations(go, onto)
        source = "GO annotations propagated over is_a/part_of with go-basic.obo"
    go = go[go["gene"].isin(network_genes)]
    sizes = go.groupby("go_id")["gene"].nunique()
    keep_terms = sizes.index[(sizes >= min_size) & (sizes <= max_size)]
    go = go[go["go_id"].isin(keep_terms)]
    genes = pd.Index(sorted(go["gene"].unique()))
    terms = pd.Index(sorted(go["go_id"].unique()))
    rows = genes.get_indexer(go["gene"])
    cols = terms.get_indexer(go["go_id"])
    matrix = sparse.csr_matrix((np.ones(len(go), dtype=np.int32), (rows, cols)), shape=(len(genes), len(terms)))
    names = pd.Series([onto.names.get(t, t) if onto else t for t in terms], index=terms, name="name")
    return TermSets(genes=genes, terms=terms, matrix=matrix, names=names, sizes=np.asarray(matrix.sum(axis=0)).ravel(), source=source)


def build_custom_term_sets(sets: dict[str, list[str]], network_genes: pd.Index) -> TermSets:
    """Curated gene sets (e.g. the secretome) as terms `SET:<name>`.

    Unlike GO, a curated set classifies the WHOLE network (a gene that is not listed is a non-member), so the
    universe is every network gene and there is no size window. Sets with no member in the network are dropped.
    """
    members = {name: [g for g in dict.fromkeys(genes) if g in set(network_genes)] for name, genes in sets.items()}
    members = {name: genes for name, genes in members.items() if genes}
    terms = pd.Index([f"SET:{name}" for name in members])
    position = {g: i for i, g in enumerate(network_genes)}
    rows = [position[g] for genes in members.values() for g in genes]
    cols = [k for k, genes in enumerate(members.values()) for _ in genes]
    matrix = sparse.csr_matrix((np.ones(len(rows), dtype=np.int32), (rows, cols)), shape=(len(network_genes), len(terms)))
    names = pd.Series([f"{name} (gene set)" for name in members], index=terms, name="name")
    return TermSets(
        genes=pd.Index(network_genes), terms=terms, matrix=matrix, names=names,
        sizes=np.asarray(matrix.sum(axis=0)).ravel(), source="curated gene sets (universe = every network gene)",
    )


def bh_adjust(p: np.ndarray, n_tests: int | None = None) -> np.ndarray:
    """Benjamini-Hochberg q-values. `n_tests` > len(p) accounts for untested hypotheses (treated as p = 1)."""
    p = np.asarray(p, dtype=np.float64)
    m = n_tests if n_tests is not None else len(p)
    order = np.argsort(p, kind="stable")
    scaled = p[order] * m / np.arange(1, len(p) + 1)
    q_sorted = np.minimum.accumulate(scaled[::-1])[::-1]
    q = np.empty_like(p)
    q[order] = np.minimum(q_sorted, 1.0)
    return q


def enrich_gene_set(query: list[str], term_sets: TermSets, alpha: float = 0.05, min_overlap: int = 2) -> pd.DataFrame:
    """Terms over-represented in `query` (a list of gene ids), sorted by q-value; only q <= alpha are returned.

    Query genes without an annotation (or outside the network) are ignored; `n_query` is the number of
    annotated query genes actually tested.
    """
    in_query = term_sets.genes.isin(list(query))
    n_query = int(in_query.sum())
    columns = ["term", "name", "overlap", "n_query", "term_size", "n_universe", "fold_enrichment", "p_value", "q_value", "genes"]
    if n_query == 0:
        return pd.DataFrame(columns=columns)
    overlap = np.asarray(term_sets.matrix.T @ in_query.astype(np.int32)).ravel()
    tested = overlap >= min_overlap
    p = np.ones(len(overlap))
    p[tested] = hypergeom.sf(overlap[tested] - 1, term_sets.n_genes, term_sets.sizes[tested], n_query)
    q = bh_adjust(p[tested], n_tests=len(overlap))
    table = pd.DataFrame(
        {
            "term": term_sets.terms[tested], "name": term_sets.names.to_numpy()[tested], "overlap": overlap[tested],
            "n_query": n_query, "term_size": term_sets.sizes[tested], "n_universe": term_sets.n_genes,
            "fold_enrichment": (overlap[tested] / n_query) / (term_sets.sizes[tested] / term_sets.n_genes),
            "p_value": p[tested], "q_value": q,
        }
    )
    table = table[table["q_value"] <= alpha].sort_values(["q_value", "p_value"]).reset_index(drop=True)
    member_genes = term_sets.genes[in_query]
    members_by_term = term_sets.matrix[np.flatnonzero(in_query), :].tocsc()
    table["genes"] = [
        ",".join(member_genes[members_by_term[:, term_sets.terms.get_loc(t)].nonzero()[0]]) for t in table["term"]
    ]
    return table[columns]


def neighbourhood_enrichment(
    neighbours: pd.DataFrame, term_sets: TermSets, alpha: float = 0.05, min_overlap: int = 3
) -> pd.DataFrame:
    """Enrichment of every gene's neighbour list, all genes at once (sparse products, no per-gene loop).

    `neighbours` needs gene_id / neighbour_id. For each gene the hypergeometric test compares its annotated
    neighbours against the annotated universe; q-values are Benjamini-Hochberg across all terms per gene
    (untested terms count as p = 1). Only q <= alpha rows are returned.
    """
    genes = pd.Index(neighbours["gene_id"].unique())
    gene_pos = genes.get_indexer(neighbours["gene_id"])
    nb_pos = term_sets.genes.get_indexer(neighbours["neighbour_id"])
    annotated = nb_pos >= 0
    # neighbour indicator (query genes x annotated genes) and the annotated-neighbour count per query gene
    adjacency = sparse.csr_matrix(
        (np.ones(annotated.sum(), dtype=np.int32), (gene_pos[annotated], nb_pos[annotated])),
        shape=(len(genes), term_sets.n_genes),
    )
    n_annotated = np.asarray(adjacency.sum(axis=1)).ravel()
    overlap = (adjacency @ term_sets.matrix).tocoo()
    keep = (overlap.data >= min_overlap) & (n_annotated[overlap.row] > 0)
    row, col, k = overlap.row[keep], overlap.col[keep], overlap.data[keep]
    columns = ["gene_id", "term", "name", "overlap", "n_neighbours_annotated", "term_size", "fold_enrichment", "p_value", "q_value"]
    if len(k) == 0:
        return pd.DataFrame(columns=columns)
    n_q, term_size = n_annotated[row], term_sets.sizes[col]
    p = hypergeom.sf(k - 1, term_sets.n_genes, term_size, n_q)
    table = pd.DataFrame({"row": row, "col": col, "k": k, "n": n_q, "K": term_size, "p": p}).sort_values(["row", "p"], kind="stable")
    rank_in_gene = table.groupby("row").cumcount().to_numpy() + 1
    scaled = table["p"].to_numpy() * len(term_sets.terms) / rank_in_gene
    # right-to-left running minimum inside each gene's block
    q = pd.Series(scaled, index=table.index).iloc[::-1].groupby(table["row"].iloc[::-1].to_numpy()).cummin().iloc[::-1].clip(upper=1.0)
    table["q"] = q.to_numpy()
    table = table[table["q"] <= alpha]
    return pd.DataFrame(
        {
            "gene_id": genes[table["row"].to_numpy()],
            "term": term_sets.terms[table["col"].to_numpy()],
            "name": term_sets.names.to_numpy()[table["col"].to_numpy()],
            "overlap": table["k"].to_numpy(),
            "n_neighbours_annotated": table["n"].to_numpy(),
            "term_size": table["K"].to_numpy(),
            "fold_enrichment": (table["k"] / table["n"] / (table["K"] / term_sets.n_genes)).to_numpy(),
            "p_value": table["p"].to_numpy(),
            "q_value": table["q"].to_numpy(),
        }
    )[columns].reset_index(drop=True)
