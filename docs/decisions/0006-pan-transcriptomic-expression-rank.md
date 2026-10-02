# 0006 — Pan-transcriptomic expression rank (biosample-level global distribution)

Status: accepted (2026-10-02). Supersedes the condition-level classification as the *methodological
reference* for gene expression behavior; the condition-level pipeline (`atlas cluster genes`,
`clustering/classify.py`) keeps running unchanged because the web app still reads its output.

## Context

The first classification (notebook v1, 2026-09-22) computed Tau, prevalence and variability on a
**condition-level median-TPM matrix** (technical replicates averaged, then median across biological
replicates per curated condition) and clustered genes with k-means. With 4 studies it selected K=2
(broad vs specific). The research question is different from what that design answers: not "how does a
gene behave across curated experimental conditions" but "considering the whole diversity of public
*A. oryzae* transcriptomes, what is the global expression behavior of each gene?" — without per-study
differential expression and without reconstructing experimental designs.

## Decision

1. **Unit of analysis = the biosample** (bioproject + biosample accession). Runs of the same biosample
   are technical re-sequencing and are averaged; the `gene_expression` table is never modified. Condition
   curation is not required (the pan-transcriptome analysis does not depend on it).
2. **Two independent axes.** Level (median log2(TPM+1)) and stability/specificity are scored separately
   (`expression_level_score`, `expression_stability_score`, `expression_specificity_score`,
   `expression_prevalence_score`); `global_expression_rank` is one explicit ordering (constitutive), never
   a hidden blend, and five other orderings are separate columns.
3. **Robust dispersion** (MAD, IQR on log2(TPM+1)); CV is secondary. Tau on log2(TPM+1) (raw-TPM Tau
   over-calls specificity; kept as `Tau_raw`).
4. **Variable vs context-specific** separated by Tau *and* peak concentration (share of total TPM in the
   top 10% of samples). Context-specific is a statistical statement, not a causal one.
5. **No absolute TPM thresholds.** Every cut-off is a quantile of the atlas' own distributions, derived at
   run time (`rank/classes.py: derive_thresholds`), saved with the output, and stress-tested by
   single-knob perturbation (`class_stability`) and by removing/capping studies and strains.
   Dispersion and Tau are ranked **within level tiers** (log-scale dispersion is compressed at low level).
6. **Heterogeneity = flags, never exclusions:** `possible_study_effect`, `possible_strain_effect`
   (majority of high-expression samples from one group and significantly more than expected,
   hypergeometric + BH), `low_sample_support`, `borderline_class`.
7. **Unsupervised structure first** (GMM, HDBSCAN, Ward) as evidence, not as the classifier: the data
   show a continuum with density concentrations, so classes are rules and the scores keep the gradient.
8. **Biology only validates** (GO/keyword gene sets, expectations stated beforehand).
9. The Tsallis/Hill q-spectrum is dropped from this module's active path (it added no clustering value
   and hurt leave-one-study-out stability in notebook v1); `aoryzae_atlas.entropy` stays, tested.

## Consequences

- Outputs are written to **new files** (`gene_expression_rank.parquet`/`.tsv.gz`,
  `gene_expression_rank_thresholds.tsv`, `gene_expression_rank_summary.json`,
  `matrices/tpm/gene_by_biosample_TPM.parquet`). `atlas rank genes` produces them (`rank/pipeline.py`
  `build_expression_rank` is the single entry point), `atlas refresh` runs it before `app export-web`, and the
  web bridge publishes `expression_rank.json` for the homepage section and the gene panel. The older
  condition-level classification (`gene_expression_behavior.parquet`) stays as the site's fallback.
- The notebook ends with a consistency check against `build_expression_rank`: if the pipeline logic changes, the
  CLI/site follow on the next `atlas refresh` and the check fails until the notebook is updated.
- Classes are **relative** by construction (tails are within-tier quantiles): a fixed share of each tier is
  always at the tails. The Intermediate class is reported instead of forcing a neighbour.
- Study and strain are partly confounded (some strains occur in a single study); flags and robustness
  checks quantify, but cannot remove, that confounding.
- Scientific code lives in `src/aoryzae_atlas/rank/` (tested in `tests/test_rank.py`); the notebook is the
  exploration/reporting layer and is re-run unchanged as studies are added.
