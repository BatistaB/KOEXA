# ADR 0005: Milestone 7 frontend stack

Date: 2026-09-21
Status: Accepted

## Context

`docs/decisions/0002-afed-audit.md` reused AFED's interface layout as the
UX benchmark for Milestone 7 (gene search, per-sample barplot, heatmap,
PCA, downloads) but explicitly deferred the implementation stack choice:
"Shiny (R) vs. a Python-native dashboard framework, given AOED's backend
is otherwise Python + DuckDB," noting that this "should get its own ADR."

The user asked to start UX/UI design work now, ahead of Milestone 7's
formal start (Milestones 1-6 aren't all validated yet -- Milestone 5 is
in progress, Milestone 6 hasn't started), providing a detailed product/UX
design brief calling for a "modern scientific instrument" interface with
design tokens, explicit component states, restrained microinteractions,
and interactive/linked data visualization -- comparable in interaction
quality to Linear, Arc, Notion, Vercel, Stripe. That brief describes a
modern web application, not a Shiny app.

## Decision

1. **React + TypeScript + Vite** for the AOED interface, not R + Shiny.
   AFED's Shiny code is not reused for the implementation; AFED's
   *interface/UX patterns* remain the benchmark per ADR 0002. This
   resolves ADR 0002's open question in favor of the Python-adjacent,
   JS-native option, since the UX brief's component-state/token/
   interaction requirements are impractical to meet in Shiny's reactive
   model, and the rest of AOED is already Python-based (DuckDB), not R.
2. Lives in `app/web/` (a new directory), not `app/aoed_shiny/` (removed
   -- it held only a `.gitkeep`, no code, so nothing is lost).
3. Charts are hand-rolled SVG rather than a charting library, per the
   Anthropic dataviz method (fixed categorical palette order, CVD-checked;
   see `app/web/README.md`) -- full control over interaction (hover,
   linked selection, log/linear toggle) matched the brief's emphasis on
   plots as first-class, inspectable interface elements.
4. Built against **fixture data** shaped exactly like the real DuckDB
   tables (`PROJECT_MASTER_SPEC.md` section 8), not a live API -- Milestone
   6 (the real multi-sample database) isn't done, and the fixture lets the
   UI/UX work proceed without blocking on it. Swapping the fixture module
   for a real fetch layer is the main integration work still needed before
   this becomes the actual Milestone 7 deliverable.

## Scope of what was built (first slice only)

MVP target item 11 ("AOED gene-expression barplot with sample metadata")
and item 4 ("AO09 canonical genes with UniProt and alias search") from
`PROJECT_MASTER_SPEC.md` section 24 -- gene search, gene identity header,
per-sample TPM plot grouped by condition and colored by study/BioProject,
sample metadata table, and a context panel for gene-level summary stats
and per-sample QC detail. Heatmap, PCA, downloadable metadata beyond the
current table, and the chromosome-TPM-map / genome-browser ideas
(documented earlier in `TODO.md`) are not built yet.

## Consequences

- A second toolchain (Node.js) is now a project dependency; installed via
  winget (`OpenJS.NodeJS.LTS`) on the user's machine.
- This is explicitly a pre-Milestone-7 UX spike, not a milestone
  completion -- `TODO.md` records it as such, not as a checked Milestone 7
  item.
