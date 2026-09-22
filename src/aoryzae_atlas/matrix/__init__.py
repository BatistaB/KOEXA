"""Gene x sample / gene x condition expression matrices (Milestone 9).

`build.py` turns the long-format `gene_expression` table into the wide
matrices the classification notebook (and, later, the frontend) consume.
`stats.py` holds the established per-gene statistics computed on top of
those matrices (abundance, prevalence, variability, Tau specificity).
"""
