"""PubMed adapter (NCBI E-utilities + iCite, no auth required).

Three-step pipeline:

1. **esearch** -- search for PMIDs matching query terms within the date window.
2. **esummary** -- batch-fetch metadata (title, journal, date, authors, DOI) for those PMIDs.
3. **iCite** -- batch-fetch citation counts and relative-citation ratios. Optional;
   skipped silently if the iCite call fails, in which case engagement defaults to 0.

The NCBI_API_KEY env var is optional. With it, rate limit is 10 req/s; without
it, 3 req/s. We only make 1 esearch per query term + 1 esummary + 1 iCite, so
rate limits aren't a problem at typical digest fan-out.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone

from digest.adapters._helpers import (
    coerce_float,
    coerce_int,
    fetch_json,
    format_authors_etal,
    parse_date_utc,
    since_date,
)
from digest.expansion import ExpandedQuery
from digest.models import Item

EUTILS_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
ICITE_URL = "https://icite.od.nih.gov/api/pubs"
PUBMED_HTML = "https://pubmed.ncbi.nlm.nih.gov"


class PubMedAdapter:
    name = "pubmed"

    def __init__(self) -> None:
        self._api_key = os.environ.get("NCBI_API_KEY", "")

    def fetch(self, query: ExpandedQuery, days: int, limit: int = 50) -> list[Item]:
        """Fetch recent PubMed papers matching any query term.

        One esearch per term (the API takes a single `term`, not a list),
        then one batched esummary + one batched iCite for all collected PMIDs.
        Dedupes by PMID; returns up to `limit` items sorted by publication date
        (newest first within each term).
        """
        mindate = since_date(days, fmt="%Y/%m/%d") or datetime.now(timezone.utc).strftime("%Y/%m/%d")
        pmids: list[str] = []
        seen_ids: set[str] = set()

        for term in query.terms:
            for pmid in self._esearch(term, mindate, limit):
                if pmid not in seen_ids:
                    seen_ids.add(pmid)
                    pmids.append(pmid)
                    if len(pmids) >= limit:
                        break
            if len(pmids) >= limit:
                break

        if not pmids:
            return []

        summaries = self._esummary(pmids)
        citations = self._icite(pmids)

        items: list[Item] = []
        for pmid in pmids:
            summary = summaries.get(pmid)
            if not summary:
                continue
            items.append(self._build_item(pmid, summary, citations.get(pmid, {})))
        return items

    def _esearch(self, term: str, mindate: str, limit: int) -> list[str]:
        params: dict[str, str] = {
            "db": "pubmed",
            "term": term,
            "retmax": str(min(limit, 100)),
            "sort": "date",
            "datetype": "pdat",
            "mindate": mindate,
            "retmode": "json",
        }
        if self._api_key:
            params["api_key"] = self._api_key
        payload = fetch_json(f"{EUTILS_URL}/esearch.fcgi", params=params, default={})
        return list(payload.get("esearchresult", {}).get("idlist", []))

    def _esummary(self, pmids: list[str]) -> dict[str, dict]:
        params: dict[str, str] = {
            "db": "pubmed",
            "id": ",".join(pmids),
            "retmode": "json",
        }
        if self._api_key:
            params["api_key"] = self._api_key
        payload = fetch_json(f"{EUTILS_URL}/esummary.fcgi", params=params, default={})
        result = payload.get("result", {}) or {}
        return {uid: result[uid] for uid in result.get("uids", []) if uid in result}

    def _icite(self, pmids: list[str]) -> dict[str, dict]:
        """Best-effort citation enrichment. Returns {} on any failure."""
        params = {
            "pmids": ",".join(pmids),
            "fl": "pmid,citation_count,relative_citation_ratio,is_clinical",
        }
        payload = fetch_json(ICITE_URL, params=params, default={})
        data = payload.get("data", []) or []
        return {str(row.get("pmid")): row for row in data if row.get("pmid") is not None}

    def _build_item(self, pmid: str, summary: dict, citation: dict) -> Item:
        title = summary.get("title") or pmid
        url = f"{PUBMED_HTML}/{pmid}/"
        # sortpubdate can be 'YYYY/MM/DD HH:MM' or 'YYYY/MM/DD' -- strip any time portion.
        sortpubdate = summary.get("sortpubdate")
        date_part = sortpubdate.split()[0] if sortpubdate else None
        timestamp = parse_date_utc(date_part, formats=("%Y/%m/%d",)) or datetime.now(timezone.utc)
        author = format_authors_etal([
            a.get("name") for a in (summary.get("authors") or [])
            if isinstance(a, dict)
        ])

        citation_count = coerce_int(citation.get("citation_count"))
        rcr = coerce_float(citation.get("relative_citation_ratio"))
        is_clinical = bool(citation.get("is_clinical"))

        doi = self._extract_doi(summary.get("articleids") or [])
        journal = summary.get("source") or summary.get("fulljournalname")
        pub_types = list(summary.get("pubtype") or [])

        return Item(
            source=self.name,
            title=title,
            url=url,
            author=author,
            timestamp=timestamp,
            engagement=citation_count,
            summary=None,
            raw={
                "pmid": pmid,
                "doi": doi,
                "journal": journal,
                "pub_types": pub_types,
                "citation_count": citation_count,
                "relative_citation_ratio": rcr,
                "is_clinical": is_clinical,
            },
        )

    @staticmethod
    def _extract_doi(articleids: list) -> str | None:
        for entry in articleids:
            if isinstance(entry, dict) and entry.get("idtype") == "doi":
                value = entry.get("value")
                if value:
                    return str(value)
        return None

