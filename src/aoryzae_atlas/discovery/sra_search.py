"""Query NCBI SRA for *A. oryzae* RNA-Seq metadata via pysradb (Milestone 2).

PROJECT_MASTER_SPEC.md sections 0/23/55 prefer `pysradb` + official
NCBI/ENA APIs over a bespoke script, and `docs/decisions/0002-afed-audit.md`
already decided against reusing AFED's own discovery approach directly
(R's `rentrez` calling `entrez_search(db='sra', term='(Aspergillus
flavus[Organism] & transcriptomic[Source]) | ...')`) for that reason. This
module reproduces the same organism + transcriptomic-strategy search intent
for *A. oryzae* through pysradb's structured `--organism`/`--strategy`
filters, which query the same underlying SRA metadata.

Discovery only fetches metadata; it never downloads FASTQ/SRA data.
"""
from __future__ import annotations

import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

ORGANISM = "Aspergillus oryzae"
STRATEGY = "RNA-Seq"
SOURCE_DB = "sra"


@dataclass(frozen=True)
class SearchProvenance:
    tool: str
    tool_version: str
    query_date_utc: str
    organism: str
    strategy: str
    source_db: str
    max_results: int
    n_rows_returned: int
    command: str


def _pysradb_version() -> str:
    result = subprocess.run(
        [sys.executable, "-m", "pysradb", "--version"],
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        check=True,
    )
    lines = result.stdout.strip().splitlines()
    return lines[-1].strip() if lines else "unknown"


def run_search(out_path: Path, max_results: int = 5000) -> SearchProvenance:
    """Run the search and save pysradb's detailed result table to `out_path`.

    This saved table *is* the preserved raw API response for this
    discovery pass (PROJECT_MASTER_SPEC.md section 23): pysradb does not
    expose the underlying wire-format response, so the fullest faithful
    capture available is its own `--detailed` (verbosity 3) output, kept
    unmodified alongside the exact query parameters recorded here.
    """
    command = [
        sys.executable,
        "-m",
        "pysradb",
        "search",
        "-O",
        ORGANISM,
        "-S",
        STRATEGY,
        "-m",
        str(max_results),
        "-d",
        SOURCE_DB,
        "--detailed",
        "-o",
        str(out_path),
    ]
    # encoding="utf-8" (not text=True, which defaults to the console's
    # locale codepage on Windows -- e.g. cp949 here -- and can crash the
    # subprocess module's own stdout-reader thread on pysradb's progress
    # bar/unicode output) with errors="replace" so a decoding hiccup in
    # output we don't otherwise use can never fail the whole search.
    subprocess.run(command, capture_output=True, encoding="utf-8", errors="replace", check=True)

    n_rows = 0
    if out_path.is_file():
        with out_path.open("r", encoding="utf-8") as fh:
            n_rows = max(sum(1 for _ in fh) - 1, 0)

    return SearchProvenance(
        tool="pysradb",
        tool_version=_pysradb_version(),
        query_date_utc=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        organism=ORGANISM,
        strategy=STRATEGY,
        source_db=SOURCE_DB,
        max_results=max_results,
        n_rows_returned=n_rows,
        command=" ".join(command),
    )
