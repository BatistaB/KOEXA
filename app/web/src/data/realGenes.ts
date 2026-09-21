import type { Gene } from "./types";
import { referenceVersion } from "./fixtures";

/**
 * Loads the real RIB40 gene catalog (public/data/genes.json, produced by
 * scripts/export_gene_catalog.py from metadata/gene_master.tsv +
 * metadata/gene_external_identifiers.tsv) — fetched at runtime rather than
 * bundled, so the ~3MB payload doesn't bloat the JS bundle and this can be
 * swapped for a real API call with no component changes later.
 */

// Row tuple index -- keep in sync with export_gene_catalog.py's COLUMNS.
const ID = 0;
const CHROMOSOME = 1;
const START = 2;
const END = 3;
const STRAND = 4;
const DESCRIPTION = 5;
const GENE_SYMBOL = 6;
const GENE_NAME = 7;
const UNIPROT = 8;
const FUNGIDB = 9;
const ALIASES_EXTRA = 10;

type GeneRow = [string, string, number, number, string, string | null, string | null, string | null, string | null, string | null, string];

interface GeneCatalogPayload {
  columns: string[];
  rows: GeneRow[];
}

export async function loadRealGenes(): Promise<Gene[]> {
  const res = await fetch("/data/genes.json");
  if (!res.ok) {
    throw new Error(`Failed to load gene catalog: ${res.status} ${res.statusText}`);
  }
  const payload = (await res.json()) as GeneCatalogPayload;
  return payload.rows.map((row): Gene => {
    const extra = row[ALIASES_EXTRA] ? row[ALIASES_EXTRA].split("|").filter(Boolean) : [];
    return {
      canonical_gene_id: row[ID],
      gene_symbol: row[GENE_SYMBOL],
      gene_name: row[GENE_NAME],
      chromosome: row[CHROMOSOME],
      start: row[START],
      end: row[END],
      strand: row[STRAND] as "+" | "-",
      biotype: "protein_coding",
      description: row[DESCRIPTION] ?? "",
      reference_version: referenceVersion,
      uniprot_accession: row[UNIPROT],
      fungidb_alt_id: row[FUNGIDB],
      aliases: extra,
    };
  });
}
