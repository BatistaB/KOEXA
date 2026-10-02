# Pan-transcriptomic gene expression rank -- A. oryzae

Generated from `notebooks/gene_expression_classification.ipynb`. Atlas scope at generation: **151 independent biological samples** (161 runs), **6 studies**, **4 strains**, **12,078 genes**.

## Design
- Unit of analysis: the biosample (technical re-sequencing runs averaged). No per-study differential expression and no condition reconstruction; study/strain effects are quality flags and robustness checks, never exclusions.
- Level and stability/specificity are separate axes; dispersion is MAD/IQR of log2(TPM+1) (CV secondary); Tau is computed on log2(TPM+1); context-specificity is statistical (Tau + peak concentration) and claims no causal condition.
- Every threshold is a quantile of the atlas' own distributions (no absolute TPM cut-offs):

| threshold                               |     value | meaning                                                                                                                                                          |
|:----------------------------------------|----------:|:-----------------------------------------------------------------------------------------------------------------------------------------------------------------|
| expressed genes (median TPM >= 0.1)     | 9810      | reference population for level quantiles                                                                                                                         |
| level_low  (Q20 of expressed)           |    1.267  | median log2(TPM+1); = 1.41 TPM; Low/Core boundary                                                                                                                |
| level_high (Q80 of expressed)           |    5.84   | median log2(TPM+1); = 56.3 TPM; Core/High boundary                                                                                                               |
| burst floor                             |   14.579  | TPM at the Q50 level of expressed genes: to count as context-specific a gene must reach at least this in one sample (become a normally expressed gene somewhere) |
| burst-capable genes                     | 9417      | reference population for the specificity quantiles                                                                                                               |
| Tau cut (Q75 of burst-capable)          |    0.638  | Context-Specific needs Tau >= this                                                                                                                               |
| peak-share cut (Q75 of burst-capable)   |    0.541  | Context-Specific needs peak share >= this                                                                                                                        |
| broad-prevalence cut (Q25 of expressed) |    0.9934 | fraction of samples with TPM >= 0.1 needed to be called 'detected everywhere'                                                                                    |
| tail quantile (dispersion, Tau)         |    0.8    | within-tier percentile above which dispersion/Tau count as high                                                                                                  |

## Classes

| expression_class   |   n_genes |   percent |
|:-------------------|----------:|----------:|
| Constitutive High  |      1363 |      11.3 |
| Constitutive Core  |      3573 |      29.6 |
| Constitutive Low   |        90 |       0.7 |
| Broad Variable     |      1642 |      13.6 |
| Context-Specific   |      1955 |      16.2 |
| Rare/Silent        |      1708 |      14.1 |
| Intermediate       |      1747 |      14.5 |

| expression_class   |   n_genes |   median_TPM |   median_logTPM |   prevalence_TPM_0.1 |   prevalence_TPM_1 |   MAD_logTPM |   IQR_logTPM |   Tau |   peak_share_top10pct |
|:-------------------|----------:|-------------:|----------------:|---------------------:|-------------------:|-------------:|-------------:|------:|----------------------:|
| Constitutive High  |      1363 |      121.088 |           6.932 |                1     |              1     |        0.437 |        0.907 | 0.187 |                 0.205 |
| Constitutive Core  |      3573 |       20.421 |           4.421 |                1     |              1     |        0.475 |        0.98  | 0.325 |                 0.242 |
| Constitutive Low   |        90 |        1.091 |           1.064 |                1     |              0.543 |        0.326 |        0.711 | 0.664 |                 0.365 |
| Broad Variable     |      1642 |       18.175 |           4.261 |                1     |              0.993 |        0.87  |        1.839 | 0.444 |                 0.377 |
| Context-Specific   |      1955 |        0.386 |           0.471 |                0.808 |              0.272 |        0.308 |        0.801 | 0.848 |                 0.812 |
| Rare/Silent        |      1708 |        0     |           0     |                0.126 |              0.013 |        0     |        0     | 0.955 |                 0.865 |
| Intermediate       |      1747 |        1.92  |           1.546 |                0.987 |              0.801 |        0.396 |        0.841 | 0.639 |                 0.415 |

Unsupervised check: BIC has no elbow up to k=10; HDBSCAN finds 2 dense cluster(s) (41% noise); rule classes vs GMM-6: ARI = 0.34. Gene behavior is a continuum with density concentrations, so the classes are rule-based and the continuous scores keep the gradient.

## Scores and rank

|                              |   expression_level_score |   expression_stability_score |   expression_specificity_score |   expression_prevalence_score |
|:-----------------------------|-------------------------:|-----------------------------:|-------------------------------:|------------------------------:|
| expression_level_score       |                     1    |                         0.52 |                          -0.86 |                          0.96 |
| expression_stability_score   |                     0.52 |                         1    |                          -0.68 |                          0.59 |
| expression_specificity_score |                    -0.86 |                        -0.68 |                           1    |                         -0.86 |
| expression_prevalence_score  |                     0.96 |                         0.59 |                          -0.86 |                          1    |

`global_expression_rank` orders genes by the constitutive score (geometric mean of level, stability, prevalence); the other orderings (`rank_most_expressed`, `rank_most_stable`, `rank_most_variable`, `rank_most_specific`, `rank_rarest`) are separate columns.

## Heterogeneity and robustness

Flags: possible_study_effect 5.5%, possible_strain_effect 4.0%, low_sample_support 0.5%, borderline_class 6.0% of genes.

| perturbation                                   |   n_samples_used |   class_agreement |   agreement_collapsing_constitutive_tiers |
|:-----------------------------------------------|-----------------:|------------------:|------------------------------------------:|
| leave out study PRJDB17490                     |              136 |             0.918 |                                     0.921 |
| leave out study PRJDB42398                     |              146 |             0.95  |                                     0.952 |
| leave out study PRJDB4747                      |              148 |             0.935 |                                     0.936 |
| leave out study PRJNA121091                    |              143 |             0.922 |                                     0.924 |
| leave out study PRJNA1261861                   |              116 |             0.879 |                                     0.885 |
| leave out strain AG-GAG                        |              111 |             0.86  |                                     0.871 |
| leave out strain AG-GAG-AOXA                   |              136 |             0.948 |                                     0.951 |
| leave out strain NS4                           |              121 |             0.902 |                                     0.907 |
| leave out strain RIB40                         |               85 |             0.598 |                                     0.607 |
| leave out study PRJDB37930 (= only RIB40)      |               66 |             0.726 |                                     0.751 |
| cap each study at 35 samples (20 random draws) |              101 |             0.868 |                                     0.878 |

Class retention under each perturbation (% of the class' genes keeping their class):

|                                                |   Constitutive High |   Constitutive Core |   Constitutive Low |   Broad Variable |   Context-Specific |   Rare/Silent |   Intermediate |
|:-----------------------------------------------|--------------------:|--------------------:|-------------------:|-----------------:|-------------------:|--------------:|---------------:|
| leave out study PRJDB17490                     |                  93 |                  94 |                 87 |               84 |                 93 |            99 |             85 |
| leave out study PRJDB42398                     |                  97 |                  96 |                 96 |               93 |                 92 |           100 |             91 |
| leave out study PRJDB4747                      |                  96 |                  95 |                 68 |               94 |                 91 |           100 |             86 |
| leave out study PRJNA121091                    |                  96 |                  95 |                 89 |               90 |                 87 |           100 |             84 |
| leave out study PRJNA1261861                   |                  91 |                  92 |                 87 |               73 |                 91 |            98 |             78 |
| leave out strain AG-GAG                        |                  89 |                  90 |                 72 |               65 |                 93 |            95 |             79 |
| leave out strain AG-GAG-AOXA                   |                  96 |                  97 |                 88 |               88 |                 97 |            98 |             90 |
| leave out strain NS4                           |                  93 |                  94 |                 77 |               76 |                 94 |            97 |             84 |
| leave out strain RIB40                         |                  79 |                  74 |                 84 |               33 |                 18 |            99 |             49 |
| leave out study PRJDB37930 (= only RIB40)      |                  76 |                  84 |                 44 |               39 |                 80 |            86 |             58 |
| cap each study at 35 samples (20 random draws) |                  90 |                  92 |                 68 |               69 |                 92 |            95 |             79 |

Structure of the atlas: for 70% of genes >= 80% of the highest-expression samples come from one strain and for 13% from one study, so per-gene flags only mark the extreme tail; the robustness table is the honest summary.

## Biological validation (after the fact)

| category               |   n_genes | expected classes                      |   fraction in expected |   fraction in all genes |   odds_ratio |   p_value |   median constitutive percentile |   q_value | supports expectation   |
|:-----------------------|----------:|:--------------------------------------|-----------------------:|------------------------:|-------------:|----------:|---------------------------------:|----------:|:-----------------------|
| translation_ribosome   |       244 | Constitutive High / Constitutive Core |                 0.8443 |                  0.4087 |       8.1419 |    0      |                           0.9016 |    0      | True                   |
| central_metabolism     |        81 | Constitutive High / Constitutive Core |                 0.5062 |                  0.4087 |       1.4871 |    0.0476 |                           0.7642 |    0.0555 | False                  |
| proteasome_ubiquitin   |       174 | Constitutive High / Constitutive Core |                 0.7644 |                  0.4087 |       4.796  |    0      |                           0.8386 |    0      | True                   |
| cytoskeleton_chromatin |       143 | Constitutive High / Constitutive Core |                 0.7972 |                  0.4087 |       5.7987 |    0      |                           0.7962 |    0      | True                   |
| stress_response        |       152 | Broad Variable / Context-Specific     |                 0.2303 |                  0.2978 |       0.7024 |    0.975  |                           0.8357 |    0.975  | False                  |
| secreted_enzymes       |       524 | Broad Variable / Context-Specific     |                 0.3626 |                  0.2978 |       1.3603 |    0.0007 |                           0.4142 |    0.0009 | True                   |
| secondary_metabolism   |       204 | Context-Specific / Rare/Silent        |                 0.6176 |                  0.3033 |       3.8076 |    0      |                           0.2325 |    0      | True                   |

## Limitations
- 6 studies with unequal sizes (largest = 56% of samples); classes are relative to this atlas and will be re-drawn as it grows.
- Study and strain are partly confounded (some strains occur in a single study).
- Validation sets use direct GO annotations and product keywords only (conservative).
- Context-specific = statistically concentrated expression, not a demonstrated condition-dependence.

## Files
- `analysis/classification/gene_expression_rank.parquet` / `.tsv.gz` -- per-gene table
- `analysis/classification/gene_expression_rank_thresholds.tsv` -- derived thresholds
- `matrices/tpm/gene_by_biosample_TPM.parquet` -- genes x independent biological samples
- `analysis/descriptive/rank_*.png` -- figures