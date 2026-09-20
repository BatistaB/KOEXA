"""Write the reports/discovery/ TSV tables and the human-readable Markdown report."""
from __future__ import annotations

from collections import Counter
from dataclasses import fields
from pathlib import Path

from .classify import DiscoveryTables
from .sra_search import SearchProvenance


def _write_tsv(rows: list, out_path: Path) -> None:
    if not rows:
        out_path.write_text("", encoding="utf-8")
        return
    header = [f.name for f in fields(rows[0])]
    with out_path.open("w", encoding="utf-8", newline="\n") as fh:
        fh.write("\t".join(header) + "\n")
        for row in rows:
            values = [str(getattr(row, name)) for name in header]
            fh.write("\t".join(v.replace("\t", " ").replace("\n", " ") for v in values) + "\n")


def write_discovery_tsvs(tables: DiscoveryTables, out_dir: Path) -> dict[str, Path]:
    paths = {
        "studies": out_dir / "studies.tsv",
        "samples": out_dir / "samples.tsv",
        "runs": out_dir / "runs.tsv",
        "exclusions": out_dir / "exclusions.tsv",
    }
    _write_tsv(tables.studies, paths["studies"])
    _write_tsv(tables.samples, paths["samples"])
    _write_tsv(tables.runs, paths["runs"])
    _write_tsv(tables.exclusions, paths["exclusions"])
    return paths


def render_markdown_report(
    tables: DiscoveryTables,
    provenance: SearchProvenance,
    crossrefs_enriched: bool = False,
) -> str:
    run_status_counts = Counter(r.status for r in tables.runs)
    sample_status_counts = Counter(s.status for s in tables.samples)
    layout_counts = Counter(r.library_layout for r in tables.runs)

    lines = [
        "# AOED discovery report -- Aspergillus oryzae RNA-Seq (SRA)",
        "",
        f"Query date (UTC): {provenance.query_date_utc}",
        f"Source API: NCBI SRA, via {provenance.tool} {provenance.tool_version}",
        f"Query: organism={provenance.organism!r}, strategy={provenance.strategy!r}, db={provenance.source_db!r}, "
        f"max_results={provenance.max_results}",
        f"Exact command: `{provenance.command}`",
        f"Rows returned: {provenance.n_rows_returned}",
        "",
        "This report is discovery output only: no FASTQ/SRA data has been "
        "downloaded, and no sample has been approved for processing "
        "(PROJECT_MASTER_SPEC.md section 23). RECOMMENDED_MVP status is not "
        "assigned automatically -- see 'Next step' below.",
        "",
        "## Counts",
        "",
        f"- BioProjects/studies: {len(tables.studies)}",
        f"- Biological samples (BioSample): {len(tables.samples)}",
        f"- Sequencing runs: {len(tables.runs)}",
        "",
        "### Run status",
        "",
    ]
    for status, count in sorted(run_status_counts.items()):
        lines.append(f"- {status}: {count}")
    lines += ["", "### Sample status", ""]
    for status, count in sorted(sample_status_counts.items()):
        lines.append(f"- {status}: {count}")
    lines += ["", "### Library layout", ""]
    for layout, count in sorted(layout_counts.items()):
        lines.append(f"- {layout or '(unresolved)'}: {count}")

    if crossrefs_enriched:
        n_geo = sum(1 for s in tables.studies if s.geo_accession)
        n_pmid = sum(1 for s in tables.studies if "PMID:" in s.notes)
        crossref_gap_line = (
            f"- GEO/PMID cross-references were resolved for all {len(tables.studies)} studies: "
            f"{n_geo} have a GEO accession, {n_pmid} have a PMID. `publication_doi`/`publication_title` "
            "are still blank even where a PMID was found -- that needs a further PMID -> article-metadata "
            "hop, not yet implemented."
        )
    else:
        crossref_gap_line = (
            "- `geo_accession`, `publication_doi`, `publication_title` in studies.tsv "
            "are blank: pysradb's per-study GEO (`srp-to-gse`) and PubMed "
            "(`srp-to-pmid`) cross-reference lookups take ~2-14s *each* and were not "
            "run for all "
            f"{len(tables.studies)} studies in this pass (would add many minutes). "
            "Re-run with `--enrich-crossrefs` to fill these in."
        )

    lines += [
        "",
        "## Known gaps in this pass (not resolved, not fabricated)",
        "",
        crossref_gap_line,
        "- AO09/RIB40 reference compatibility risk (spec section 23) is not yet "
        "assessed per study -- that requires the condition_clues/strain text "
        "to be read, which is a human curation step.",
        "- No automated 'RECOMMENDED_MVP' selection: spec section 23 asks for a "
        "manually approved, diverse representative set (submerged/solid-state, "
        "carbon sources, stress, growth phase, strain); every study/sample/run "
        "that passed basic checks is marked REQUIRES_REVIEW instead.",
        "",
        "## Next step",
        "",
        "Review reports/discovery/studies.tsv and samples.tsv, pick a small "
        "diverse set for Milestone 5's first end-to-end sample, and approve "
        "explicitly (`atlas sample approve <SRR>`, once Milestone 4 exists) -- "
        "discovery does not approve anything on its own.",
    ]
    return "\n".join(lines) + "\n"
