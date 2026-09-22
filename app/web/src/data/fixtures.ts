/**
 * The atlas now runs entirely on real data (data/realGenes.ts's
 * genes.json + data/realAtlas.ts's datasets/conditions/samples/sample_qc/
 * expression/classification.json, all produced by `atlas app export-web`
 * -- see src/aoryzae_atlas/webexport/build.py).
 *
 * `referenceVersion` is the one constant that stays hand-set here rather
 * than coming from a fetched file: it's the FungiDB annotation build the
 * gene catalog's coordinates are versioned against (metadata/gene_master.
 * tsv's own reference_version column), which is NOT the same string as a
 * sample's reference_version (e.g. "RIB40_v1", the Salmon quantification
 * index build) -- two genuinely different "reference" concepts that
 * happen to share a field name. Keep this in sync with gene_master.tsv if
 * the genome annotation is ever re-frozen at a new FungiDB release.
 */
export const referenceVersion = "FungiDB_v71";
