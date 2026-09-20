# AOED discovery report -- Aspergillus oryzae RNA-Seq (SRA)

Query date (UTC): 2026-09-20T15:54:54+00:00
Source API: NCBI SRA, via pysradb python.exe -m pysradb 2.5.1
Query: organism='Aspergillus oryzae', strategy='RNA-Seq', db='sra', max_results=5000
Exact command: `D:\PanTranscriptome\.venv\Scripts\python.exe -m pysradb search -O Aspergillus oryzae -S RNA-Seq -m 5000 -d sra --detailed -o D:\PanTranscriptome\reports\discovery\raw_api_responses\sra_search_2026-09-20.tsv`
Rows returned: 458

This report is discovery output only: no FASTQ/SRA data has been downloaded, and no sample has been approved for processing (PROJECT_MASTER_SPEC.md section 23). RECOMMENDED_MVP status is not assigned automatically -- see 'Next step' below.

## Counts

- BioProjects/studies: 58
- Biological samples (BioSample): 439
- Sequencing runs: 458

### Run status

- EXCLUDE: 1
- REQUIRES_REVIEW: 457

### Sample status

- EXCLUDE: 1
- REQUIRES_REVIEW: 438

### Library layout

- PAIRED: 408
- SINGLE: 50

## Known gaps in this pass (not resolved, not fabricated)

- `geo_accession`, `publication_doi`, `publication_title` in studies.tsv are blank: pysradb's per-study GEO (`srp-to-gse`) and PubMed (`srp-to-pmid`) cross-reference lookups take ~2-14s *each* and were not run for all 58 studies in this pass (would add many minutes). A follow-up enrichment pass can fill these in.
- AO09/RIB40 reference compatibility risk (spec section 23) is not yet assessed per study -- that requires the condition_clues/strain text to be read, which is a human curation step.
- No automated 'RECOMMENDED_MVP' selection: spec section 23 asks for a manually approved, diverse representative set (submerged/solid-state, carbon sources, stress, growth phase, strain); every study/sample/run that passed basic checks is marked REQUIRES_REVIEW instead.

## Next step

Review reports/discovery/studies.tsv and samples.tsv, pick a small diverse set for Milestone 5's first end-to-end sample, and approve explicitly (`atlas sample approve <SRR>`, once Milestone 4 exists) -- discovery does not approve anything on its own.
