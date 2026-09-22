# Gene Expression Behavior Classification -- A. oryzae Transcriptome Atlas

Generated from `notebooks/gene_expression_classification.ipynb`. Pilot run: 41 samples, 17 conditions, 4 studies, 12,078 genes.

## Part A -- Established analysis

### Methodology
Tau (Kryuchkova-Mostacci & Robinson-Rechavi 2017, doi:10.1093/bib/bbw008), substituting biological condition for tissue. Computed on the condition-level median-TPM matrix (technical replicates collapsed by mean, then median across true biological replicates), never on raw per-SRR values.

### Abundance, prevalence, variability
- Abundance: median condition-level TPM, right-skewed as expected; log10 transform used downstream.
- Prevalence: computed at 0.1/1/5 TPM; Spearman agreement across thresholds (see `analysis/descriptive/prevalence_thresholds.png`).
- Variability: robust_CV (1.4826*MAD/median) preferred over CV, which is unstable near zero mean; NaN (not 0) reported when undefined.

### Specificity (Tau)
- n genes with both Tau_raw and Tau_log1p defined: 11,933
- Spearman(Tau_raw, Tau_log1p) = 0.880
- Genes >=0.9 specific: raw=2,474 (20.7%) vs log1p=846 (7.1%) -- raw TPM inflates apparent specificity, consistent with Kryuchkova-Mostacci & Robinson-Rechavi's own finding for Tau.
- Primary statistic: Tau_log1p (see Section 4 rationale).

### Distributions and clustering
- Tau_log1p modality: best-fitting Gaussian-mixture component count (BIC) = 3.
- BASE clustering: K_BASE = 2 (silhouette-selected); cross-method agreement ARI(KMeans,GMM) = 0.755, ARI(KMeans,Agglomerative) = 0.701.

### Cluster stability
- Subsampling (80% of genes, 30 reps): mean ARI = 0.999
- Bootstrap (resample with replacement, 30 reps): mean ARI = 0.997
- Leave-one-study-out ARI (BASE):
|             |   n_conditions_remaining |   n_genes_clustered |   ARI_vs_full_model |
|:------------|-------------------------:|--------------------:|--------------------:|
| PRJDB17490  |                       12 |               11180 |            0.853822 |
| PRJDB42398  |                       12 |               10694 |            0.864663 |
| PRJDB4747   |                       14 |               10989 |            0.87022  |
| PRJNA121091 |                       13 |               10830 |            0.857552 |

### Biological interpretation (provisional)
| biological_label   |   n_genes |
|:-------------------|----------:|
| constitutive_high  |      7542 |
| condition_specific |      3344 |
| nan                |      1192 |

No gene is labeled `housekeeping_candidate` by this notebook; that label requires independent functional/annotation evidence beyond expression behavior alone (see Section 14).

## Part B -- Tsallis experiment (secondary, exploratory)

### Definition
Gene-centric Tsallis/Hill entropy, q in {0.5, 1, 2, 3, 4}, computed over each gene's proportion of its own total TPM across conditions -- a reinterpretation of Derian et al. 2022 (doi:10.1371/journal.pone.0266618), whose original application computes entropy over each SAMPLE's whole gene distribution, not a gene's distribution across conditions. Not an established gene-classification method.

### Relationship with Tau
| D_column   |     n |   spearman_rho_vs_Tau_log1p |   p_value |
|:-----------|------:|----------------------------:|----------:|
| D_0.5      | 11933 |                   -0.929718 |         0 |
| D_1        | 11933 |                   -0.925035 |         0 |
| D_2        | 11933 |                   -0.912901 |         0 |
| D_3        | 11933 |                   -0.903254 |         0 |
| D_4        | 11933 |                   -0.896786 |         0 |

Top Tau-vs-D1 rank-disagreement genes: AO090673000002, AO090011000840, AO090005000619, AO090023000757, AO090026000440 (see `analysis/entropy/disagreement_gene_profiles.png` for their condition-level TPM profiles).

### Does the q-spectrum add information?
- Silhouette at K_BASE: BASE = 0.547, EXTENDED = 0.500
- ARI(BASE clusters, EXTENDED clusters) = 0.541
- Leave-one-study-out ARI, BASE vs EXTENDED:
|             |   ARI_BASE |   ARI_EXTENDED |
|:------------|-----------:|---------------:|
| PRJDB17490  |   0.853822 |       0.764359 |
| PRJDB42398  |   0.864663 |       0.726129 |
| PRJDB4747   |   0.87022  |       0.775508 |
| PRJNA121091 |   0.857552 |       0.776304 |

### Limitations
- Pilot dataset: 4 studies, 17 conditions, 41 samples; 8 of 17 conditions have a single biological replicate.
- q is a tunable sensitivity parameter here, not a validated biological constant.
- Conclusions should be re-tested once Milestone 8 broadens study/condition coverage.

## Central scientific question
Can the condition-wide expression landscape of *A. oryzae* reveal reproducible gene-expression archetypes? This pilot's answer, to be re-tested at scale: see the cluster-stability numbers above. Whether the Tsallis q-spectrum adds information beyond the established framework is answered directly by the BASE-vs-EXTENDED comparison above -- and the atlas and established classification remain useful regardless of that answer.