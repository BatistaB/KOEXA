"""Export the real RIB40 gene catalog into a compact JSON the web app can
fetch, for UX/UI stress-testing at full-genome scale (12,090 genes) ahead
of Milestone 6's real expression data.

Reads metadata/gene_master.tsv (coordinates/description, one row per gene)
and metadata/gene_external_identifiers.tsv (UniProt accession + protein
name, FungiDB alt ID, curated short aliases -- see Milestone 1 in
TODO.md), joins them per gene, and writes app/web/public/data/genes.json
as an array of compact tuples (not objects -- avoids repeating field names
12,090 times). gene_symbol/gene_name are blank in gene_master.tsv itself
(recorded there deliberately, see TODO.md Milestone 1); this script fills
gene_symbol from a gene_alias row when one exists (706 of 12,090 genes)
and gene_name from the UniProtKB_accession row's protein-name field
(populated for all 12,099 mapped genes) -- better display names than
guessing, not fabricated.

Run from the repo root: python app/web/scripts/export_gene_catalog.py
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
GENE_MASTER = REPO_ROOT / "metadata" / "gene_master.tsv"
EXTERNAL_IDS = REPO_ROOT / "metadata" / "gene_external_identifiers.tsv"
OUT_PATH = REPO_ROOT / "app" / "web" / "public" / "data" / "genes.json"

# Tuple column order shipped to the frontend -- keep in sync with
# app/web/src/data/realGenes.ts's GENE_ROW_* index constants.
COLUMNS = [
    "canonical_gene_id",
    "chromosome",
    "start",
    "end",
    "strand",
    "description",
    "gene_symbol",
    "gene_name",
    "uniprot_accession",
    "fungidb_alt_id",
    "aliases_extra",
]


def load_identifiers() -> dict[str, dict[str, list[str]]]:
    by_gene: dict[str, dict[str, list[str]]] = {}
    with EXTERNAL_IDS.open(encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh, delimiter="\t")
        for row in reader:
            namespace = row["namespace"]
            if namespace not in ("UniProtKB_accession", "gene_alias", "FungiDB"):
                continue
            gene_id = row["canonical_gene_id"]
            bucket = by_gene.setdefault(gene_id, {})
            if namespace == "UniProtKB_accession":
                bucket.setdefault("uniprot", []).append(row["external_id"])
                if row.get("external_name"):
                    bucket.setdefault("uniprot_name", []).append(row["external_name"])
            elif namespace == "gene_alias":
                bucket.setdefault("alias", []).append(row["external_id"])
            elif namespace == "FungiDB":
                bucket.setdefault("fungidb", []).append(row["external_id"])
    return by_gene


def main() -> None:
    identifiers = load_identifiers()
    rows: list[list] = []

    with GENE_MASTER.open(encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh, delimiter="\t")
        for row in reader:
            gene_id = row["canonical_gene_id"]
            ids = identifiers.get(gene_id, {})
            aliases = ids.get("alias", [])
            gene_symbol = aliases[0] if aliases else None
            aliases_extra = "|".join(aliases[1:]) if len(aliases) > 1 else ""
            uniprot_names = ids.get("uniprot_name", [])
            gene_name = uniprot_names[0] if uniprot_names else None
            uniprot = ids.get("uniprot", [])
            fungidb = ids.get("fungidb", [])

            rows.append([
                gene_id,
                row["chromosome"],
                int(row["start"]),
                int(row["end"]),
                row["strand"],
                row["description"] or None,
                gene_symbol,
                gene_name,
                uniprot[0] if uniprot else None,
                fungidb[0] if fungidb else None,
                aliases_extra,
            ])

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with OUT_PATH.open("w", encoding="utf-8") as fh:
        json.dump({"columns": COLUMNS, "rows": rows}, fh, separators=(",", ":"), ensure_ascii=False)

    symbol_count = sum(1 for r in rows if r[6])
    name_count = sum(1 for r in rows if r[7])
    print(f"Wrote {len(rows)} genes to {OUT_PATH}")
    print(f"  with gene_symbol: {symbol_count} ({symbol_count / len(rows):.1%})")
    print(f"  with gene_name:   {name_count} ({name_count / len(rows):.1%})")
    print(f"  file size: {OUT_PATH.stat().st_size / 1024:.0f} KB")


if __name__ == "__main__":
    main()
