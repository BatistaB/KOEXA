"""Import, resolve, store and load curated gene sets.

A gene set is a biological *annotation* supplied by the user (for instance the proteins with a signal peptide
and a cell-wall/extracellular location). It never defines an expression class: the expression classes of
`atlas rank genes` come from the atlas' own distributions, and a gene set is overlaid on them afterwards.

Identifiers are resolved conservatively (AGENTS.md: ambiguous mappings stay ambiguous):

* `exact`      the token is a current canonical gene id;
* `redirected` the token is a retired AO09 id that FungiDB's GeneAliases.txt redirects to exactly one current
               gene (the project's vetted redirect map, `identifiers.fungidb.build_ao09_redirect_map`);
* `manual`     the user stated the mapping explicitly (`--map TOKEN=GENE`);
* `alias_candidate`  the token is only known as an alias in the identifier table: candidates are listed, NOT accepted;
* `unresolved` nothing matches.

Only the first three put a gene in the set. Everything is written to a resolution table so a reader can see
exactly how each input token was treated.
"""
from __future__ import annotations

import json
import re
from datetime import date
from pathlib import Path

import pandas as pd

__all__ = [
    "ACCEPTED_RESOLUTIONS",
    "parse_gene_list",
    "resolve_gene_list",
    "write_gene_set",
    "load_gene_set",
    "load_gene_sets",
    "alias_candidates_from_table",
]

ACCEPTED_RESOLUTIONS = ("exact", "redirected", "manual")
_SPLIT = re.compile(r"[\s,;]+")
_NAME = re.compile(r"^[a-z][a-z0-9_]*$")


def parse_gene_list(text: str) -> list[str]:
    """Tokens of a pasted gene list: whitespace/comma/semicolon separated, `#` starts a comment; order and duplicates kept."""
    tokens: list[str] = []
    for line in text.splitlines():
        tokens.extend(t for t in _SPLIT.split(line.split("#", 1)[0].strip()) if t)
    return tokens


def alias_candidates_from_table(external_identifiers: pd.DataFrame) -> dict[str, list[str]]:
    """alias token -> canonical gene ids, from the `gene_alias` rows of metadata/gene_external_identifiers.tsv."""
    aliases = external_identifiers[external_identifiers["namespace"] == "gene_alias"]
    out: dict[str, set[str]] = {}
    for gene_id, alias in zip(aliases["canonical_gene_id"], aliases["external_id"]):
        out.setdefault(str(alias), set()).add(str(gene_id))
    return {alias: sorted(genes) for alias, genes in out.items()}


def resolve_gene_list(
    tokens: list[str],
    catalog_ids: set[str],
    redirect_map: dict[str, str] | None = None,
    alias_candidates: dict[str, list[str]] | None = None,
    manual_map: dict[str, str] | None = None,
) -> pd.DataFrame:
    """One row per distinct token (first-seen order): resolution, accepted canonical id (or '') and candidates/notes."""
    redirect_map, alias_candidates, manual_map = redirect_map or {}, alias_candidates or {}, manual_map or {}
    bad_manual = {t: g for t, g in manual_map.items() if g not in catalog_ids}
    if bad_manual:
        raise ValueError(f"manual mappings point to genes that are not in the catalog: {bad_manual}")
    counts: dict[str, int] = {}
    for token in tokens:
        counts[token] = counts.get(token, 0) + 1
    rows = []
    for token, n in counts.items():
        if token in manual_map:
            resolution, gene, note = "manual", manual_map[token], "mapping stated by the user"
        elif token in catalog_ids:
            resolution, gene, note = "exact", token, ""
        elif token in redirect_map:
            resolution, gene, note = "redirected", redirect_map[token], "retired AO09 id redirected by FungiDB GeneAliases.txt"
        elif token in alias_candidates:
            resolution, gene, note = "alias_candidate", "", "alias only, NOT accepted; candidates: " + ";".join(alias_candidates[token])
        else:
            resolution, gene, note = "unresolved", "", "no match in the gene catalog, redirect map or alias table"
        rows.append({"input_id": token, "n_occurrences": n, "resolution": resolution, "canonical_gene_id": gene, "note": note})
    return pd.DataFrame(rows, columns=["input_id", "n_occurrences", "resolution", "canonical_gene_id", "note"])


def write_gene_set(
    name: str, resolution: pd.DataFrame, out_dir: Path, description: str, source: str, raw_text: str, n_tokens: int
) -> dict:
    """Write `<name>.tsv` (members), `<name>.resolution.tsv`, `<name>.json` (metadata) and `<name>.input.txt` (as supplied)."""
    if not _NAME.match(name):
        raise ValueError("gene set names are lowercase letters, digits and underscores, starting with a letter")
    out_dir.mkdir(parents=True, exist_ok=True)
    accepted = resolution[resolution["resolution"].isin(ACCEPTED_RESOLUTIONS)]
    members = (
        accepted.groupby("canonical_gene_id", sort=False)
        .agg(input_ids=("input_id", lambda s: ";".join(s)), resolution=("resolution", lambda s: ";".join(dict.fromkeys(s))))
        .reset_index()
    )
    members.to_csv(out_dir / f"{name}.tsv", sep="\t", index=False)
    resolution.to_csv(out_dir / f"{name}.resolution.tsv", sep="\t", index=False)
    (out_dir / f"{name}.input.txt").write_text(raw_text if raw_text.endswith("\n") else raw_text + "\n", encoding="utf-8")
    meta = {
        "name": name,
        "description": description,
        "source": source,
        "imported_on": date.today().isoformat(),
        "n_input_lines": n_tokens,
        "n_distinct_tokens": int(len(resolution)),
        "n_duplicate_lines": int(n_tokens - len(resolution)),
        "n_by_resolution": {k: int(v) for k, v in resolution["resolution"].value_counts().items()},
        "n_members": int(len(members)),
    }
    (out_dir / f"{name}.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    return meta


def load_gene_set(name: str, directory: Path) -> list[str]:
    """Canonical gene ids of one stored set."""
    return pd.read_csv(directory / f"{name}.tsv", sep="\t", dtype=str)["canonical_gene_id"].tolist()


def load_gene_sets(directory: Path) -> dict[str, dict]:
    """Every stored set as {name: {"meta": {...}, "genes": [...]}} (empty when the directory does not exist)."""
    if not directory.is_dir():
        return {}
    sets = {}
    for meta_file in sorted(directory.glob("*.json")):
        name = meta_file.stem
        if (directory / f"{name}.tsv").is_file():
            sets[name] = {"meta": json.loads(meta_file.read_text(encoding="utf-8")), "genes": load_gene_set(name, directory)}
    return sets
