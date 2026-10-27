# Gene Ontology (go-basic.obo)

Used by `aoryzae_atlas.coexpr` (`atlas coexpr build|query`) to propagate FungiDB GO annotations to ancestor
terms (is_a / part_of) and to give GO terms readable names. See `docs/decisions/0008-coexpression-network.md`.

- File: `go-basic.obo` (not tracked in git; see `.gitignore`)
- Source: https://current.geneontology.org/ontology/go-basic.obo (via https://purl.obolibrary.org/obo/go/go-basic.obo)
- Downloaded: 2026-10-14, with the user's explicit approval
- Ontology release (`data-version`): `releases/2026-07-26`
- Size: 32,227,785 bytes; 16,272 `[Term]` stanzas
- SHA-256: `b08d45b268b8c24ccb2513dbbbc7d4df9f6521c099b413f79eb31e06e0fa3bcc`

To update: re-download over the same path, record the new `data-version` and checksum here, then run
`atlas coexpr build` (or `atlas refresh`) so enrichment is recomputed against the new release.
