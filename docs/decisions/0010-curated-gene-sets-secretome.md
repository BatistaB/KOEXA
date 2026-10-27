# 0010 — Curated gene sets (first one: the secretome)

Status: accepted (2026-10-26). Implemented in `src/aoryzae_atlas/genesets/`; `atlas geneset import|list`;
analysis in `notebooks/secretome.ipynb`.

## Context

The user supplied a list of 1,235 genes judged to be secreted (signal peptide from SignalP 6.0 plus the UniProt
"cell wall" annotation) and asked for a "secreted" class to look at them in the atlas. Two things made a plain
"add a class" the wrong shape:

- The seven expression classes of `atlas rank genes` are derived from the atlas' own distributions and, by design
  (ADR 0006), biology never defines them. "Secreted" is a biological annotation, a different axis.
- The list is a pasted set of identifiers, some from a retired annotation (AO09 ids renumbered by FungiDB v71),
  one gene symbol and one alias. Identifiers must resolve conservatively (AGENTS.md: ambiguous mappings stay
  ambiguous; never fabricate).

## Decision

1. **A gene set is a curated annotation overlaid on the classes, not a class.** It is stored as small tracked files
   under `metadata/gene_sets/`: `<name>.tsv` (members), `<name>.resolution.tsv` (how every input token was treated),
   `<name>.json` (description, source text recorded verbatim, counts) and `<name>.input.txt` (the list as supplied).
   `atlas geneset import NAME FILE --description ... --source ... [--map TOKEN=GENE]` writes them; no database
   migration (the study-groups work owns the migration sequence) and no change to the rank table.
2. **Resolution is conservative.** Accepted: current canonical ids (`exact`); retired AO09 ids that FungiDB's
   GeneAliases.txt redirects to exactly one current gene (`redirected`, the project's existing vetted map);
   mappings the user states explicitly (`manual`). Aliases are listed as candidates and never accepted;
   unknown tokens stay `unresolved`. Several tokens reaching one gene collapse to one member.
3. **Consumers read the sets from one place.** (a) `atlas coexpr build` adds each set as a `SET:<name>` term in a
   separate enrichment family (universe = every network gene, no size window, kept apart from GO), written to
   `coexpression_gene_set_enrichment.parquet`; `atlas coexpr query` prints it too. (b) `atlas app export-web`
   writes `gene_sets.json`; the homepage "Global expression behavior" section gets a "Show: All genes / <Set> only"
   toggle that restricts every view to the set (the note on the page states that the classes were derived from all
   genes), and the gene panel lists the sets a gene belongs to.
4. **The first set, `secreted`, is the user's list as supplied.** 1,235 lines -> 1,234 distinct ids -> 1,223
   genes (1,191 exact, 41 retired ids redirected onto 32 genes; nine current genes are reached by two retired ids
   each, i.e. merged loci). `sspB` had no match in any identifier table; the user mapped it to AO090038000546 (2026-10-26, `--map`), a gene already in the set as a direct id. Not accepted: `AO090011000795-A` (an alias
   whose only candidate, AO090011000795, is annotated as a vacuolar polyphosphate kinase, not the dipeptidyl
   peptidase the alias names -- accepting it would label a vacuolar gene as secreted). It waits for the user.

## Consequences

- The set records the *union* of two evidence sources; per-gene evidence (SignalP vs UniProt) was not supplied, so
  the set cannot be split into "predicted secreted", "cell wall" and "both" until that is provided.
- `notebooks/secretome.ipynb` checks the list against GO cellular-component annotation (GO is incomplete and partly
  inferred, so it is a plausibility check): the members are strongly enriched in extracellular/cell-wall terms, a
  small share is annotated only to intracellular compartments, and the genes reached through retired ids look less
  secreted-like than directly matched ones (borderline significance, 32 genes) -- flagged for a manual look.
- Further sets (transporters, transcription factors, ...) need no new code: import another list.
- Expression classes are unchanged and still relative to the atlas; the overlay only changes which genes are shown.
