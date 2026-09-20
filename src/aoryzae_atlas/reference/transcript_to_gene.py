"""Build the transcript-to-gene (t2g) mapping from the FungiDB transcript FASTA.

Needed to aggregate Salmon's transcript-level quantification up to AO09
gene-level TPM/counts (PROJECT_MASTER_SPEC.md section 9's "transcript-to-gene
aggregation" step). nf-core/rnaseq does not derive this for a custom
non-Ensembl reference, so it is AOED-specific derived metadata, not a
reimplementation of anything nf-core/Salmon already does.
"""
from __future__ import annotations

import re
from pathlib import Path

_HEADER_FIELDS = re.compile(r"^>(?P<transcript_id>\S+)\s*\|\s*gene=(?P<gene_id>AO09\d{10})")


def load_transcript_to_gene(transcript_fasta_path: Path) -> list[tuple[str, str]]:
    """Return (transcript_id, gene_id) pairs, one per protein-coding-gene FASTA record.

    The file also carries 274 non-coding RNA transcripts (tRNA/ncRNA genes
    with a "t0000N"-style, non-AO09 gene id, e.g. "AO090005t00001"); those
    don't match the AO09 pattern and are intentionally skipped, consistent
    with the rest of Milestone 1/3 being scoped to the 12,090 protein-coding
    AO09 genes. In this v71 release every protein-coding gene has exactly
    one transcript record (verified 2026-09-20: pair count == distinct gene
    count), so this is also, incidentally, a 1:1 mapping here.
    """
    pairs: list[tuple[str, str]] = []
    with transcript_fasta_path.open("r", encoding="utf-8") as fh:
        for line in fh:
            if not line.startswith(">"):
                continue
            match = _HEADER_FIELDS.match(line)
            if match:
                pairs.append((match.group("transcript_id"), match.group("gene_id")))
    return pairs


def write_t2g_tsv(pairs: list[tuple[str, str]], out_path: Path) -> None:
    with out_path.open("w", encoding="utf-8", newline="\n") as fh:
        fh.write("transcript_id\tgene_id\n")
        for transcript_id, gene_id in pairs:
            fh.write(f"{transcript_id}\t{gene_id}\n")
