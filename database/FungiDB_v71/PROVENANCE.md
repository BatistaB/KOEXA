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

## Open provenance question (not yet answered -- do not assume)

`Archive_9_PSIM_Aory.xlsx` is the "UniProt-derived workbook" referenced in
`TODO.md` / `PROJECT_MASTER_SPEC.md` section 12. Its internal metadata shows
it was built with `openpyxl`, last edited by the user, but the exact UniProt
query behind it (reference proteome ID, taxon, query string, retrieval date)
has not been confirmed. Until answered, `reference_version` in
`metadata/gene_id_mapping.tsv` is recorded as `FungiDB_v71` (the AO09
evidence snapshot being reconciled against), not a UniProt release/date,
per the "never invent versions" rule in `AGENTS.md`.
