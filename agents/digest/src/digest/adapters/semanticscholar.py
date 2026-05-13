"""Semantic Scholar adapter (api.semanticscholar.org, key optional).

One search request per query term against `/paper/search`, dedupe by paperId.
The `tldr` field carries an AI-generated summary we surface as `Item.summary`.

Rate limit notes:
- Unauthenticated: ~100 req/5min, hits 429 quickly under bursty calls.
- With `S2_API_KEY` (header `x-api-key`): 1 RPS, much more predictable.
- The adapter treats 429 as soft-fail: the failing term is skipped, the rest
  of the terms are tried, and we return whatever we collected. This keeps
  multi-term digest queries useful even when one query exhausts the limit.

The bulk endpoint (`/paper/search/bulk`) is cheaper but doesn't support the
`tldr` field, which is the single most useful enrichment for digest summaries.
Trade-off: prefer `/paper/search` and accept the lower per-call limit.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone

import httpx

from digest.adapters._helpers import (
    coerce_int,
    cutoff_datetime,
    format_authors_etal,
    parse_date_utc,
)
from digest.expansion import ExpandedQuery
from digest.models import Item

SEARCH_URL = "https://api.semanticscholar.org/graph/v1/paper/search"
PAPER_HTML = "https://www.semanticscholar.org/paper"

FIELDS = [
    "title",
    "authors",
    "year",
    "citationCount",
    "influentialCitationCount",
    "tldr",
    "externalIds",
    "publicationDate",
    "venue",
    "openAccessPdf",
    "url",
]


class SemanticScholarAdapter:
    name = "semanticscholar"

    def __init__(self) -> None:
        self._api_key = os.environ.get("S2_API_KEY", "")

    def fetch(self, query: ExpandedQuery, days: int, limit: int = 50) -> list[Item]:
        """Fetch papers matching any query term.

        Runs one /paper/search per term. Dedupes by paperId. Returns up to
        `limit` items. The `days` parameter only matters indirectly: S2 has
        no native publication-date filter in /paper/search, so we filter
        client-side by `publicationDate`.
        """
        cutoff = cutoff_datetime(days)
        per_term = max(min(limit, 100), 1)
        seen: dict[str, Item] = {}

        for term in query.terms:
            for paper in self._search(term, per_term):
                paper_id = paper.get("paperId")
                if not paper_id or paper_id in seen:
                    continue
                pub_date = parse_date_utc(paper.get("publicationDate"))
                if cutoff and pub_date and pub_date < cutoff:
                    continue
                seen[paper_id] = self._build_item(paper, pub_date)
                if len(seen) >= limit:
                    return list(seen.values())

        return list(seen.values())[:limit]

    def _search(self, term: str, limit: int) -> list[dict]:
        params = {
            "query": term,
            "limit": str(limit),
            "fields": ",".join(FIELDS),
        }
        headers = {"x-api-key": self._api_key} if self._api_key else {}

        try:
            response = httpx.get(SEARCH_URL, params=params, headers=headers, timeout=30.0)
        except httpx.HTTPError:
            return []

        if response.status_code == 429:
            # Soft-fail: rate-limited, skip this term but keep going.
            return []
        try:
            response.raise_for_status()
            payload = response.json()
        except (httpx.HTTPError, ValueError):
            return []
        return payload.get("data", []) or []

    def _build_item(self, paper: dict, pub_date: datetime | None) -> Item:
        paper_id = paper["paperId"]

        title = paper.get("title") or paper_id
        url = paper.get("url") or f"{PAPER_HTML}/{paper_id}"

        timestamp = pub_date or self._year_to_datetime(paper.get("year")) or datetime.now(timezone.utc)

        author = format_authors_etal([
            a.get("name") for a in (paper.get("authors") or [])
            if isinstance(a, dict)
        ])

        citation_count = coerce_int(paper.get("citationCount"))
        influential = coerce_int(paper.get("influentialCitationCount"))
        engagement = citation_count + influential * 5

        tldr_text = self._extract_tldr(paper.get("tldr"))

        oa_url = self._extract_oa_url(paper.get("openAccessPdf"))

        return Item(
            source=self.name,
            title=title,
            url=url,
            author=author,
            timestamp=timestamp,
            engagement=engagement,
            summary=tldr_text,
            raw={
                "paperId": paper_id,
                "citationCount": citation_count,
                "influentialCitationCount": influential,
                "tldr": tldr_text,
                "year": paper.get("year"),
                "externalIds": paper.get("externalIds") or {},
                "venue": paper.get("venue"),
                "openAccessPdf": oa_url,
            },
        )

    @staticmethod
    def _year_to_datetime(year: object) -> datetime | None:
        """Fallback when publicationDate is missing: use year midpoint."""
        if year is None:
            return None
        try:
            y = int(year)
        except (ValueError, TypeError):
            return None
        return datetime(y, 7, 1, tzinfo=timezone.utc)

    @staticmethod
    def _extract_tldr(value: object) -> str | None:
        """Pull `.text` from the tldr object, or return a string as-is."""
        if value is None:
            return None
        if isinstance(value, dict):
            text = value.get("text")
            return text if isinstance(text, str) and text else None
        if isinstance(value, str):
            return value or None
        return None

    @staticmethod
    def _extract_oa_url(value: object) -> str | None:
        """Pull a usable URL out of the openAccessPdf object; ignore empty strings."""
        if value is None:
            return None
        if isinstance(value, dict):
            url = value.get("url")
            return url if isinstance(url, str) and url else None
        if isinstance(value, str):
            return value or None
        return None

