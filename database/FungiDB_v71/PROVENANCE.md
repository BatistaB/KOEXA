# FungiDB v71 evidence files (Milestone 1 input)

Payload files in this directory are excluded from git (see `.gitignore`);
only this file and `CHECKSUMS.sha256` are tracked. Verify local files with:

```bash
sha256sum -c CHECKSUMS.sha256
```

## Known provenance

- Source: FungiDB, release 71 (https://fungidb.org).
- Organism/strain: *Aspergillus oryzae* RIB40.
- Files: `FungiDB-71_AoryzaeRIB40*` (genome annotation GFF, annotated
  CDS/protein/transcript FASTAs, curated and computed GO association files,
  gene aliases, gene-product-description updates) -- supplied by the user
  2026-09-20.
- Structural validation (record counts, checksums) recorded by
  `atlas identifiers reconcile`; see `reports/gene_id_mapping_summary.txt`.
- `FungiDB-71_AoryzaeRIB40_Genome.fasta` (supplied 2026-09-20): 12
  sequences (8 chromosomes, 3 unplaced contigs, 1 mitochondrial genome),
  37,912,014 bp total. Verified against NCBI's Assembly database
  (`esearch`/`esummary`, db=assembly, term="Aspergillus oryzae
  RIB40"[organism], 2026-09-20): matches **GCF_000184455.2** (assembly
  name ASM18445v3, RefSeq category "reference genome", submitter NITE
  Japan) -- NCBI's own nuclear-genome total (37,882,812 bp, via the
  `datasets` API) plus the 29,202 bp mitochondrial genome equals our file's
  total exactly (37,912,014 bp). The 3 other RIB40 assemblies found
  (GCA_000965245.1/ASM96524v1, a contig-level AIST resequencing with a
  different total length and no chromosome-level assembly; and the older
  GCA_000184455.2/ASM18445v2 and GCF_000184455.1/ASM18445v1) do not match.
  Structural validation (`atlas reference validate`) confirmed the GFF's
  12,090 protein-coding genes match the protein FASTA's gene set exactly,
  and the transcript-to-gene mapping's genes are a subset of the GFF's.
  See `reports/reference_validation.txt`.
- The annotation (GFF `source` column = "VEuPathDB") is FungiDB/VEuPathDB's
  own curation, not verbatim NCBI RefSeq gene models -- it does not have a
  separate NCBI-style accession distinct from its FungiDB release number
  (71), which is why `config/reference.yaml`'s `annotation_accession`
  stays null even after freezing (see that file's own comment).

## Open provenance question (not yet answered -- do not assume)

`Archive_9_PSIM_Aory.xlsx` is the "UniProt-derived workbook" referenced in
`TODO.md` / `PROJECT_MASTER_SPEC.md` section 12. Its internal metadata shows
it was built with `openpyxl`, last edited by the user, but the exact UniProt
query behind it (reference proteome ID, taxon, query string, retrieval date)
has not been confirmed. Until answered, `reference_version` in
`metadata/gene_id_mapping.tsv` is recorded as `FungiDB_v71` (the AO09
evidence snapshot being reconciled against), not a UniProt release/date,
per the "never invent versions" rule in `AGENTS.md`.
