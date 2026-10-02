"""Pan-transcriptomic gene expression rank (global expression behavior).

Treats the whole atlas as one heterogeneous collection of independent
biological samples (biosamples) and characterizes how each gene behaves
across it -- no per-study differential expression, no per-condition
reconstruction. Modules:

- `metrics`     per-gene distribution metrics (level, prevalence, dispersion, Tau, peak concentration)
- `scores`      continuous level / stability / specificity / prevalence scores and rank orderings
- `classes`     quantile-derived thresholds and the rule-based expression classes
- `diagnostics` study/strain dominance flags (quality flags, never automatic exclusion)
- `validation`  post-hoc biological sanity checks against GO / product annotation
- `pipeline`    DuckDB -> per-gene table, the single entry point used by `atlas rank genes`, `atlas refresh`
                and the notebook's consistency check (change the pipeline there, nowhere else)
"""
