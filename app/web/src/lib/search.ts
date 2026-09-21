import type { Gene } from "../data/types";

export interface GeneSearchHit {
  gene: Gene;
  matchedOn: string;
  score: number;
}

/**
 * Ranked substring search over canonical ID, symbol, name, aliases,
 * UniProt accession, and FungiDB alt ID — mirrors the AO09/UniProt/name/
 * alias search target in PROJECT_MASTER_SPEC.md section 24 item 4.
 * Runs over the full gene catalog (real genome scale, ~12k genes) on
 * every keystroke, so this stays a flat per-gene field scan — no
 * secondary map/array to join against.
 */
export function searchGenes(query: string, genes: Gene[]): GeneSearchHit[] {
  const q = query.trim().toLowerCase();
  if (!q) return [];

  const hits: GeneSearchHit[] = [];

  for (const gene of genes) {
    let best: { field: string; score: number } | null = null;

    const consider = (value: string | null, field: string, weight: number) => {
      if (!value) return;
      const v = value.toLowerCase();
      let score = 0;
      if (v === q) score = 100 * weight;
      else if (v.startsWith(q)) score = 70 * weight;
      else if (v.includes(q)) score = 40 * weight;
      if (score > 0 && (!best || score > best.score)) {
        best = { field, score };
      }
    };

    consider(gene.canonical_gene_id, gene.canonical_gene_id, 1);
    consider(gene.gene_symbol, gene.gene_symbol ?? "", 1.2);
    consider(gene.gene_name, gene.gene_name ?? "", 0.9);
    consider(gene.uniprot_accession, `UniProt: ${gene.uniprot_accession}`, 0.85);
    consider(gene.fungidb_alt_id, `FungiDB: ${gene.fungidb_alt_id}`, 0.8);
    for (const alias of gene.aliases) {
      consider(alias, `alias: ${alias}`, 0.85);
    }

    if (best) {
      hits.push({ gene, matchedOn: (best as { field: string }).field, score: (best as { score: number }).score });
    }
  }

  return hits.sort((a, b) => b.score - a.score);
}
