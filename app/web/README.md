# AOED web

React + TypeScript + Vite frontend for the *A. oryzae* Expression
Database (AOED). See `docs/decisions/0005-milestone7-frontend-stack.md`
at the repo root for why this stack was chosen over the AFED-derived
R/Shiny reference implementation, and `PROJECT_MASTER_SPEC.md` section 24
for the product scope this is working toward.

## Status

First slice only. Home view stacks three sections: a gene-ranking overview
(every gene, summed TPM across samples, stacked bar per gene colored by
study, most to least expressed, with a zoom control for how many genes to
show); a gene expression classification donut (biological_label counts
from `atlas cluster genes`, provisional at pilot scale); and a
chromosome-wide expression map (all 8 RIB40 chromosomes at true relative
length, binned mean TPM as a sequential heatmap). Clicking a bar, a donut
slice, or a chromosome region — or searching by AO09 ID / symbol / name /
alias / UniProt accession — opens a gene detail view (per-sample TPM bar
chart, grouped by condition, colored by study). Strain and condition are
both optional filters in the top bar that scope every chart.

Runs entirely on real data, fetched at runtime rather than bundled (every
component consumes the `Gene`/`Sample`/`Condition`/`Dataset`/
`GeneExpressionRow`/`GeneClassification` shapes from `src/data/types.ts`,
not a data-loading module directly):

- `public/data/genes.json` (`src/data/realGenes.ts`) — the full RIB40 gene
  catalog, from `metadata/gene_master.tsv` +
  `metadata/gene_external_identifiers.tsv`.
- `public/data/{datasets,conditions,samples,sample_qc,expression,
  classification,chromosome_expression}.json` (`src/data/realAtlas.ts`) —
  real DuckDB-backed samples/conditions/studies/expression, the Tau/
  cluster-based gene classification, and the binned whole-genome
  expression map, for only the samples that are pipeline-QUANTIFIED **and**
  condition-curated.

Both are gitignored and regenerated, never hand-edited — see "Running"
below. There is no synthetic/fixture data path anymore; a gene or sample
that hasn't been through the real pipeline simply doesn't appear.

## Running

```bash
npm install
cd .. && atlas refresh   # from the repo root: regenerates every public/data/*.json
cd app/web && npm run dev
```

`atlas refresh` (see `src/aoryzae_atlas/cli/main.py` at the repo root) is
the standardized one-command pipeline: DB migrate/load → ingest → matrix
build → gene statistics → entropy → clustering → `atlas app export-web`.
Run it after adding studies/samples to the atlas, any time you want the
site to reflect the latest data. Its last step alone
(`atlas app export-web`) is enough if you just want to re-export
already-computed matrices/classification without recomputing them.

Or preview from the repo root via the Claude Code browser preview config
(`.claude/launch.json`, name `aoed-web`) — run `atlas refresh` first.

## Design notes

- No charting library — both `src/components/gene/ExpressionChart.tsx`
  (per-gene) and `src/components/overview/GeneRankingChart.tsx` (all
  genes, stacked) are hand-rolled SVG bar charts, for full control over
  linked hover/selection between chart and table.
- Categorical/status colors follow the Anthropic dataviz skill's
  validated default palette (fixed hue order, checked for CVD-safe
  adjacent-pair contrast) — see `src/styles/tokens.css`.
- QC-flagged samples are never marked by color alone: a warning-triangle
  glyph above the bar on the charts, plus an icon + text badge in the
  table (`src/components/common/StatusBadge.tsx`).
- The ranking chart is deliberately linear-only (no log toggle): it's a
  *stack* of per-sample segments, and a log scale would distort each
  segment's visual proportion of the total. The per-gene chart keeps the
  linear/log toggle since each bar there is one independent value.
