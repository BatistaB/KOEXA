"""Automatic evidence collection for a study's paper and design.

`atlas annotate collect` runs this for every study that has samples but no
evidence file yet. It gathers -- but never decides -- what a curator needs
to write metadata/study_annotations/<BIOPROJECT>.json:

1. Paper candidates linked at the *accession level* only:
   * NCBI elink BioProject -> PubMed (submitter-declared link), and
   * Europe PMC full-text search for the BioProject / SRA study / GEO
     series accession.
   A title/keyword search is deliberately not used: it finds papers *about*
   the same topic, not the paper that produced these reads.
2. For each candidate: title, authors, year, journal, DOI, PMID, PMCID and
   abstract (Europe PMC core metadata), and -- when the paper is open
   access -- the sentences of its full text that mention the accession.
   Those snippets are what distinguishes "the data were deposited under
   PRJDB4747" (the originating paper) from a later paper that merely
   re-analysed the data; `deposition_statement` flags the former.
3. The study's own SRA sample titles/attributes (reports/discovery) and
   curated conditions (metadata/conditions.tsv).

Full texts are not stored (only short accession-context snippets), and
nothing here writes the curated annotation itself.
"""
from __future__ import annotations

import html
import json
import re
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

__all__ = ["collect_study_evidence", "deposition_snippets", "write_evidence"]

EUTILS = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/"
EUROPEPMC = "https://www.ebi.ac.uk/europepmc/webservices/rest/"
USER_AGENT = "aoryzae-atlas/0.1 (KOEXA study annotation)"
_DEPOSIT_WORDS = re.compile(
    r"deposit|data availability|available (?:in|at|under|from)|accession (?:code|number|no)|"
    r"generated in this study|submitted to|have been (?:uploaded|archived)",
    re.IGNORECASE,
)


def _get_json(url: str, params: dict[str, Any], pause: float = 0.34) -> Any:
    full = url + "?" + urllib.parse.urlencode(params)
    request = urllib.request.Request(full, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=60) as response:
        payload = json.loads(response.read().decode("utf-8"))
    time.sleep(pause)  # NCBI: <= 3 requests/s without an API key
    return payload


def _get_text(url: str) -> str | None:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=90) as response:
            return response.read().decode("utf-8", errors="replace")
    except Exception:  # noqa: BLE001 -- full text is best-effort
        return None


def _strip_markup(text: str) -> str:
    # Europe PMC titles arrive with entity-escaped markup (&lt;i&gt;), so
    # unescape first, then strip tags, then unescape what the tags hid.
    text = re.sub(r"</?(?:i|b|em|strong|sup|sub|sc|italic|bold)(?:\s[^>]*)?>", "", html.unescape(text))
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", html.unescape(text)).strip()


def deposition_snippets(full_text: str, accessions: list[str], width: int = 220) -> list[dict[str, Any]]:
    """Context around each accession mention; `deposition_statement` marks data-availability wording."""
    snippets: list[dict[str, Any]] = []
    for accession in accessions:
        for match in re.finditer(re.escape(accession), full_text):
            window = full_text[max(0, match.start() - width): match.end() + width // 2]
            snippets.append({
                "accession": accession,
                "text": window,
                "deposition_statement": bool(_DEPOSIT_WORDS.search(window)),
            })
            if len(snippets) >= 6:
                return snippets
    return snippets


def _pubmed_links(bioproject: str) -> list[str]:
    search = _get_json(EUTILS + "esearch.fcgi", {"db": "bioproject", "term": f"{bioproject}[PRJA]", "retmode": "json"})
    uids = search.get("esearchresult", {}).get("idlist", [])
    pmids: list[str] = []
    for uid in uids[:1]:
        links = _get_json(EUTILS + "elink.fcgi", {"dbfrom": "bioproject", "db": "pubmed", "id": uid, "retmode": "json"})
        for linkset in links.get("linksets", []):
            for db in linkset.get("linksetdbs", []):
                pmids.extend(str(x) for x in db.get("links", []))
    return pmids


def _europepmc_accession_hits(accessions: list[str]) -> dict[str, list[str]]:
    """{pmid_or_id: [accessions it mentions]} from Europe PMC full-text search."""
    hits: dict[str, list[str]] = {}
    for accession in accessions:
        payload = _get_json(EUROPEPMC + "search", {"query": f'"{accession}"', "format": "json", "pageSize": 25}, pause=0.2)
        for result in payload.get("resultList", {}).get("result", []):
            key = result.get("pmid") or result.get("id")
            if key:
                hits.setdefault(str(key), []).append(accession)
    return hits


def _europepmc_core(pmid: str) -> dict[str, Any] | None:
    payload = _get_json(
        EUROPEPMC + "search", {"query": f"EXT_ID:{pmid}", "format": "json", "resultType": "core"}, pause=0.2
    )
    results = payload.get("resultList", {}).get("result", [])
    return results[0] if results else None


def _candidate(pmid: str, found_by: list[str], accessions: list[str]) -> dict[str, Any]:
    core = _europepmc_core(pmid) or {}
    pmcid = core.get("pmcid")
    snippets: list[dict[str, Any]] = []
    if pmcid and core.get("isOpenAccess") == "Y":
        xml = _get_text(f"{EUROPEPMC}{pmcid}/fullTextXML")
        if xml:
            snippets = deposition_snippets(_strip_markup(xml), accessions)
    doi = core.get("doi")
    return {
        "pmid": core.get("pmid") or pmid,
        "pmcid": pmcid,
        "doi": doi,
        "title": _strip_markup(core.get("title") or ""),
        "authors": core.get("authorString"),
        "year": int(core["pubYear"]) if str(core.get("pubYear", "")).isdigit() else None,
        "journal": (core.get("journalInfo") or {}).get("journal", {}).get("title"),
        "url": f"https://doi.org/{doi}" if doi else (f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/" if pmid else None),
        "open_access": core.get("isOpenAccess") == "Y",
        "abstract": _strip_markup(core.get("abstractText") or ""),
        "found_by": sorted(set(found_by)),
        "accession_snippets": snippets,
        "deposition_statement": any(s["deposition_statement"] for s in snippets),
    }


def _study_context(bioproject: str, discovery_dir: Path, conditions_tsv: Path, samples_tsv: Path) -> dict[str, Any]:
    context: dict[str, Any] = {}
    studies_path = discovery_dir / "studies.tsv"
    if studies_path.is_file():
        studies = pd.read_csv(studies_path, sep="\t", dtype=str, keep_default_na=False)
        row = studies[studies["bioproject"] == bioproject]
        if not row.empty:
            context["study"] = row.iloc[0].to_dict()
    discovery_samples = discovery_dir / "samples.tsv"
    if discovery_samples.is_file():
        frame = pd.read_csv(discovery_samples, sep="\t", dtype=str, keep_default_na=False)
        frame = frame[frame["bioproject"] == bioproject]
        context["sra_samples"] = frame[["biosample", "sample_title", "strain", "condition_clues"]].to_dict(orient="records")
    if samples_tsv.is_file():
        samples = pd.read_csv(samples_tsv, sep="\t", dtype=str, keep_default_na=False)
        samples = samples[samples["bioproject"] == bioproject]
        context["atlas_samples"] = samples[["sample_id", "biosample", "condition_id", "strain"]].to_dict(orient="records")
        if conditions_tsv.is_file():
            conditions = pd.read_csv(conditions_tsv, sep="\t", dtype=str, keep_default_na=False)
            conditions = conditions[conditions["condition_id"].isin(set(samples["condition_id"]))]
            context["curated_conditions"] = [
                {k: v for k, v in record.items() if v} for record in conditions.to_dict(orient="records")
            ]
    return context


def collect_study_evidence(
    bioproject: str,
    discovery_dir: Path,
    conditions_tsv: Path,
    samples_tsv: Path,
) -> dict[str, Any]:
    context = _study_context(bioproject, discovery_dir, conditions_tsv, samples_tsv)
    study = context.get("study", {})
    accessions = [a for a in (bioproject, study.get("study_accession"), study.get("geo_accession")) if a]

    found: dict[str, list[str]] = {}
    for pmid in _pubmed_links(bioproject):
        found.setdefault(pmid, []).append("ncbi_elink_bioproject_pubmed")
    for pmid, mentioned in _europepmc_accession_hits(accessions).items():
        found.setdefault(pmid, []).extend(f"europepmc_fulltext:{a}" for a in mentioned)

    candidates = [_candidate(pmid, sources, accessions) for pmid, sources in found.items()]
    # Originating paper first: deposition statement, then elink, then oldest
    # (a re-analysis is necessarily published after the data).
    candidates.sort(key=lambda c: (
        not c["deposition_statement"],
        "ncbi_elink_bioproject_pubmed" not in c["found_by"],
        c["year"] or 9999,
    ))
    return {
        "bioproject": bioproject,
        "collected_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "accessions_searched": accessions,
        "method": "NCBI elink bioproject->pubmed + Europe PMC full-text accession search; "
                  "open-access full texts scanned for accession/deposition sentences",
        "paper_candidates": candidates,
        "suggested_paper_status": (
            "found" if candidates and (candidates[0]["deposition_statement"]
                                       or "ncbi_elink_bioproject_pubmed" in candidates[0]["found_by"])
            else ("ambiguous" if candidates else "not_found")
        ),
        **context,
    }


def write_evidence(evidence: dict[str, Any], out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{evidence['bioproject']}.json"
    path.write_text(json.dumps(evidence, indent=2, ensure_ascii=False), encoding="utf-8")
    return path
