"""Minimal genome FASTA reader (sequence names/lengths only, no sequence loading)."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class GenomeSequence:
    name: str
    length: int


def load_genome_sequence_lengths(genome_fasta_path: Path) -> list[GenomeSequence]:
    """Return (name, length) per FASTA record, counting bases (not the header's own `length=` field)."""
    sequences: list[GenomeSequence] = []
    current_name: str | None = None
    current_length = 0
    with genome_fasta_path.open("r", encoding="utf-8") as fh:
        for line in fh:
            if line.startswith(">"):
                if current_name is not None:
                    sequences.append(GenomeSequence(current_name, current_length))
                current_name = line[1:].split()[0]
                current_length = 0
            else:
                current_length += len(line.strip())
        if current_name is not None:
            sequences.append(GenomeSequence(current_name, current_length))
    return sequences
