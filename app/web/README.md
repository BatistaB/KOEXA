# AOED web

React + TypeScript + Vite frontend for the *A. oryzae* Expression
Database (AOED). See `docs/decisions/0005-milestone7-frontend-stack.md`
at the repo root for why this stack was chosen over the AFED-derived
R/Shiny reference implementation, and `PROJECT_MASTER_SPEC.md` section 24
for the product scope this is working toward.

## Status

First slice only. Home view is a gene-ranking overview (every gene, summed
TPM across samples, stacked bar per gene colored by study, most to least
expressed); clicking a bar — or searching by AO09 ID / symbol / name /
alias / UniProt accession — opens a gene detail view (per-sample TPM bar
chart, grouped by condition, colored by study). Strain and condition are
both optional filters in the top bar that scope every chart. Built against
`src/data/fixtures.ts` — data shaped exactly like
the real DuckDB tables (`PROJECT_MASTER_SPEC.md` section 8) but with
invented accessions and hand-tuned (not measured) TPM values, since the
real atlas only has a handful of samples ingested so far (Milestone 5,
in progress). Swap `src/data/fixtures.ts` for a real API/DuckDB-backed
fetch layer once Milestone 6 closes — every component consumes the
`Gene`/`Sample`/`Condition`/`Dataset`/`GeneExpressionRow` shapes from
`src/data/types.ts`, not the fixture module directly, so that swap
shouldn't require touching component code.

Gene catalog: 9 hand-curated "hero" genes with a real biological story
(condition-dependent TPM) live in `src/data/fixtures.ts`, merged at
startup with the real 12,090-gene RIB40 catalog fetched from
`public/data/genes.json` (`src/data/realGenes.ts`) — for UX/UI
stress-testing at full-genome scale ahead of Milestone 6. Genes outside
the curated 9 get deterministic *synthetic* filler TPM
(`src/lib/syntheticExpression.ts`, no biological story, just a plausible
long-tailed distribution) since real full-genome quantification doesn't
exist yet.

## Running

```bash
npm install
python scripts/export_gene_catalog.py   # generates public/data/genes.json
npm run dev
```

`public/data/genes.json` is gitignored (~3MB, reproducible from
`metadata/gene_master.tsv` + `metadata/gene_external_identifiers.tsv` at
the repo root) — regenerate it after a fresh clone, or whenever those
source TSVs change.

Or from the repo root, via the Claude Code browser preview config
(`.claude/launch.json`, name `aoed-web`).

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
