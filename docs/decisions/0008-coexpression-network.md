# 0008 — Gene co-expression network (AFED-style, adapted to a multi-study atlas)

Status: accepted (2026-10-14). Implemented in `src/aoryzae_atlas/coexpr/`; command `atlas coexpr build|query`,
also run by `atlas refresh`; exploration/reporting in `notebooks/coexpression_network.ipynb`.

## Context

AFED (Database 2025, baaf033) offers a co-expression network built from samples with >= 10 M mapped reads, genes
with mean TPM >= 1 and Pearson r >= 0.5 with **no batch correction**, queried by one gene or a gene set and
summarised by functional enrichment of the co-expressed genes. AOED is a much more heterogeneous collection
(dozens of studies, laboratories and strains), so the same recipe cannot be assumed to behave the same way.
Before building anything a feasibility benchmark (scratch, 16 workflow variants) was run on the real atlas using
AFED's own yardstick: do genes of one functional group correlate more than random gene pairs (AUC)?

Findings that shaped the design (numbers from the 279-biosample atlas, 2026-10-14; the notebook recomputes them live):

- A depth cut-off at 10 M assigned reads kept 226/279 biosamples and changed recovery very little; 20 M kept 106
  and was worse. The cut-off is a parameter, not a finding.
- With every study pooled, 12-16 % of **random** gene pairs exceed |r| >= 0.5 (study/strain offsets); centering
  each gene per study brought that to 6-8 % and raised ribosome/proteasome recovery. It lowered recovery of
  secondary-metabolism genes, whose co-variation is **between** studies. Neither mode dominates.
- Pearson vs Spearman made almost no difference.

## Decision

1. **Unit = biosample**, as everywhere (technical-replicate runs averaged; `gene_expression` untouched).
2. **Depth filter on gene-assigned reads:** `salmon_total_gene_assigned_counts` summed over a biosample's runs,
   default 10 M (`--min-reads-millions`). Unknown depth never passes a positive cut-off.
3. **Genes:** mean TPM >= 1 over the selected biosamples; the **same gene universe in every mode**.
4. **Two modes** built on the same genes/biosamples: `all_samples` (AFED-style, pooled, no correction) and
   `within_study` (per-gene centering of log2(TPM+1) inside each study with >= 3 biosamples). Correlation is
   **Spearman** by default (`--method pearson` available).
5. **No fixed |r| cut-off.** The output is a directed top-N neighbour list per gene (default 50) where each edge
   carries `rank`, `r`, `reverse_rank`, `mutual_rank` (sqrt of the two ranks, ATTED-II), `bg_tail` (fraction of
   random gene pairs with r at least this large), `within_study_median_r` and `n_studies_tested` (the same
   correlation recomputed inside single studies — an independent reliability check). Network edges are cut on
   these columns by the consumer through `network.select_edges` (the notebook uses mutual rank <= 2, plus
   within-study support >= 0.2 for the pooled mode). The cut-off matters a lot: on the current atlas the graph is
   a set of small modules at mutual rank <= 2 and merges into one giant component by <= 3-5 (percolation), so a
   loose cut gives a hairball. `r` and `bg_tail` alone are weak edge criteria: the random-pair background in a
   structured atlas is wide (its 99th percentile is above the r of many rank-50 neighbours).
6. **Enrichment:** hypergeometric (one-sided Fisher) over GO terms from the FungiDB GAF, Benjamini-Hochberg across
   all eligible terms per gene, universe = annotated network genes, terms limited to 5-500 genes. With
   `database/GeneOntology/go-basic.obo` (downloaded 2026-10-14 with the user's approval, release 2026-07-26; see
   its PROVENANCE.md) annotations propagate over is_a/part_of and terms get names; without the file only direct
   annotations and bare GO ids are used (unit-tested on a miniature OBO). Propagation makes terms of one lineage
   non-independent, so several significant terms for a gene often describe the same thing. Enrichment is computed
   for every gene's neighbourhood at once and for arbitrary gene sets (`atlas coexpr query`).
7. **Gene sets as queries:** `coexpressed_with_set` ranks genes by mean r to the members and reports `min_r`.
8. **Quality monitor:** every run re-computes the functional-group AUC benchmark per mode and stores it
   (`coexpression_benchmark.tsv`); the random-pair background statistics go to the summary JSON.
9. **Refusal instead of guessing:** fewer than 20 selected biosamples (or a mode left with fewer after the
   per-study filter) raises `CoexpressionNotPossibleError`; `atlas refresh` reports the step as SKIPPED.

## Consequences

- Outputs: `analysis/coexpression/coexpression_neighbours.parquet` (both modes, `mode` column),
  `coexpression_enrichment.parquet` (only when GO annotations exist), `coexpression_benchmark.tsv`,
  `coexpression_summary.json` (scope, parameters, background statistics, depth table), and standardized profiles
  `matrices/coexpression/zscores_<mode>.parquet` (so set queries and the future web app need no database).
  Parquet/PNG stay gitignored; the small TSV/JSON are tracked like the rank outputs.
- `pipeline.build_coexpression` is the single entry point (CLI, refresh and the notebook's consistency check). If the
  workflow changes, change it there; the notebook's last cell fails until the notebook is brought back in line.
- Memory: the rank matrix is `uint16` (G x G, ~0.3 GB for 12 k genes); runtime ~45 s for 10 k genes x 226 biosamples.
- Not done here (deliberately): web export / network view (the edge table is the data contract), community
  detection, size-factor normalisation on counts instead of TPM.
- Limitations are stated in the notebook: TPM is compositional; study/strain are partly confounded; GO coverage is
  partial; benchmark groups are crude and have no confidence interval.
