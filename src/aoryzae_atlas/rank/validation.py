"""Post-hoc biological validation of the classes (never used to define them).

Gene sets come from direct GO annotations (FungiDB GAF, no ancestor propagation)
and from product-description keywords. Both are deliberately conservative
sanity-check sets, not a functional-enrichment analysis: the question is only
whether well-understood gene groups land in biologically coherent regions of the
ranking, e.g. ribosomal proteins among constitutive genes.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import fisher_exact

from .diagnostics import benjamini_hochberg

__all__ = ["GO_CATEGORIES", "PRODUCT_KEYWORDS", "load_go_annotations", "build_gene_sets", "class_enrichment"]

GO_CATEGORIES: dict[str, set[str]] = {
    "translation_ribosome": {
        "GO:0006412", "GO:0005840", "GO:0003735", "GO:0022626", "GO:0006414", "GO:0002181",
        "GO:0015934", "GO:0015935", "GO:0022625", "GO:0022627",
    },
    "central_metabolism": {"GO:0006096", "GO:0006099", "GO:0006094", "GO:0006098"},
    "proteasome_ubiquitin": {"GO:0000502", "GO:0005839", "GO:0006511", "GO:0004298"},
    "stress_response": {"GO:0006950", "GO:0006457", "GO:0006979", "GO:0009408", "GO:0006986", "GO:0051082"},
    "secreted_enzymes": {"GO:0005576", "GO:0004553", "GO:0004556", "GO:0004339", "GO:0008810"},
    "secondary_metabolism": {"GO:0019748", "GO:0044550", "GO:0017000", "GO:0030639", "GO:0043386"},
}

PRODUCT_KEYWORDS: dict[str, str] = {
    "translation_ribosome": r"ribosomal protein|elongation factor|translation initiation factor|ribosome",
    "central_metabolism": (
        r"glyceraldehyde|phosphoglycerate|enolase|pyruvate kinase|fructose-bisphosphate aldolase|triosephosphate|"
        r"citrate synthase|isocitrate dehydrogenase|malate dehydrogenase|succinate dehydrogenase|fumarate hydratase|"
        r"phosphofructokinase|hexokinase"
    ),
    "proteasome_ubiquitin": r"proteasome|ubiquitin",
    "stress_response": r"heat shock|chaperon|hsp\d+|catalase|superoxide dismutase|peroxiredoxin",
    "secreted_enzymes": (
        r"alpha-amylase|glucoamylase|cellulase|xylanase|pectin|pectate lyase|lipase|tannase|phytase|chitinase|"
        r"cutinase|laccase"
    ),
    "secondary_metabolism": r"polyketide synthase|non-?ribosomal peptide synthe|terpene (?:synthase|cyclase)|aflatoxin|ustiloxin|kojic",
    "cytoskeleton_chromatin": r"\bactin\b|tubulin|histone",
}


def load_go_annotations(gaf_path: Path) -> pd.DataFrame:
    """(gene, go_id) pairs from a GAF 2.x file; 'NOT' qualifiers and comment lines are skipped."""
    rows = []
    with Path(gaf_path).open(encoding="utf-8") as fh:
        for line in fh:
            if line.startswith("!"):
                continue
            parts = line.rstrip("\n").split("\t")
            if len(parts) < 5 or "NOT" in parts[3]:
                continue
            rows.append((parts[1], parts[4]))
    return pd.DataFrame(rows, columns=["gene", "go_id"]).drop_duplicates()


def build_gene_sets(go: pd.DataFrame, descriptions: pd.Series, universe: pd.Index) -> pd.DataFrame:
    """Boolean gene x category table (GO hit OR product-keyword hit), restricted to `universe`."""
    out = pd.DataFrame(index=universe)
    descriptions = descriptions.reindex(universe).fillna("").str.lower()
    categories = list(dict.fromkeys([*GO_CATEGORIES, *PRODUCT_KEYWORDS]))
    for category in categories:
        by_go = pd.Series(False, index=universe)
        if category in GO_CATEGORIES:
            genes = go.loc[go["go_id"].isin(GO_CATEGORIES[category]), "gene"].unique()
            by_go = pd.Series(universe.isin(genes), index=universe)
        by_keyword = pd.Series(False, index=universe)
        if category in PRODUCT_KEYWORDS:
            by_keyword = descriptions.str.contains(PRODUCT_KEYWORDS[category], regex=True)
        out[category] = by_go | by_keyword
    return out


def class_enrichment(classes: pd.Series, gene_sets: pd.DataFrame, rank_percentile: pd.Series) -> pd.DataFrame:
    """Per (category, class): n, fraction of the category, odds ratio vs. all other genes, BH q.

    `rank_percentile` is the constitutive-rank percentile (1 = most constitutive); its
    per-category median summarizes where the category sits in the global ranking.
    """
    classes = classes.astype(str)
    records = []
    for category in gene_sets.columns:
        members = gene_sets[category].reindex(classes.index).fillna(False).to_numpy()
        n_members = int(members.sum())
        if n_members == 0:
            continue
        median_pct = float(np.nanmedian(rank_percentile.to_numpy()[members]))
        for cls in pd.unique(classes):
            in_class = (classes == cls).to_numpy()
            a = int((members & in_class).sum())
            b = int((members & ~in_class).sum())
            c = int((~members & in_class).sum())
            d = int((~members & ~in_class).sum())
            odds, p = fisher_exact([[a, b], [c, d]])
            records.append(
                {
                    "category": category,
                    "class": cls,
                    "n_category": n_members,
                    "n_in_class": a,
                    "fraction_of_category": a / n_members,
                    "odds_ratio": odds,
                    "p_value": p,
                    "category_median_constitutive_percentile": median_pct,
                }
            )
    table = pd.DataFrame(records)
    table["q_value"] = benjamini_hochberg(table["p_value"].to_numpy())
    return table
