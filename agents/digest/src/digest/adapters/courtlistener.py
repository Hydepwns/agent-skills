"""CourtListener adapter (courtlistener.com /api/rest/v4/search, token optional).

Searches the `opinions` index (`type=o`) -- case law -- one request per term.
Dedupes by `cluster_id` so different judges' opinions on the same case don't
take multiple digest slots.

Auth: `COURTLISTENER_TOKEN` env var grants 5,000 req/hr via header
`Authorization: Token {token}`. Anonymous requests also work in practice
(despite docs saying auth required) but get a lower rate ceiling.

Engagement = `citeCount` (number of times the opinion is cited by others).
The SCOTUS bonus lives in `credibility._per_item_bonus`: opinions with
`court_id == "scotus"` get +0.3 on top of the citeCount thresholds.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone

from digest.adapters._helpers import (
    coerce_int,
    fetch_json,
    format_authors_etal,
    parse_date_utc,
    since_date,
)
from digest.expansion import ExpandedQuery
from digest.models import Item

API_URL = "https://www.courtlistener.com/api/rest/v4/search/"
SITE_BASE = "https://www.courtlistener.com"


class CourtListenerAdapter:
    name = "courtlistener"

    def __init__(self) -> None:
        self._token = os.environ.get("COURTLISTENER_TOKEN", "")

    def fetch(self, query: ExpandedQuery, days: int, limit: int = 50) -> list[Item]:
        """Fetch recent opinions matching any query term.

        One /search/ call per term, dedupe by cluster_id. Returns up to
        `limit` items in dateFiled-desc order. Uses native `filed_after`
        filter when `days > 0`.
        """
        since = since_date(days)
        seen: dict[str, Item] = {}

        for term in query.terms:
            for result in self._search(term, since, limit):
                cluster_id = self._coerce_str(result.get("cluster_id"))
                if not cluster_id or cluster_id in seen:
                    continue
                seen[cluster_id] = self._build_item(result, cluster_id)
                if len(seen) >= limit:
                    return list(seen.values())

        return list(seen.values())[:limit]

    def _search(self, term: str, since: str | None, limit: int) -> list[dict]:
        params: dict[str, str] = {
            "q": term,
            "type": "o",
            "order_by": "dateFiled desc",
        }
        if since:
            params["filed_after"] = since

        headers = {"Authorization": f"Token {self._token}"} if self._token else {}
        payload = fetch_json(API_URL, params=params, headers=headers, default={})
        return (payload.get("results") or [])[:limit]

    def _build_item(self, result: dict, cluster_id: str) -> Item:
        case_name = result.get("caseName") or cluster_id
        absolute_url = result.get("absolute_url") or ""
        url = self._build_url(absolute_url)

        cite_count = coerce_int(result.get("citeCount"))

        court_id = result.get("court_id") or ""
        court = result.get("court") or court_id or None

        timestamp = parse_date_utc(result.get("dateFiled")) or datetime.now(timezone.utc)

        snippet = result.get("snippet") or None

        return Item(
            source=self.name,
            title=case_name,
            url=url,
            author=self._format_judges(result.get("judge")),
            timestamp=timestamp,
            engagement=cite_count,
            summary=snippet,
            raw={
                "cluster_id": cluster_id,
                "caseName": case_name,
                "court": court,
                "court_id": court_id,
                "dateFiled": result.get("dateFiled"),
                "citeCount": cite_count,
                "citation": result.get("citation") or [],
                "docketNumber": result.get("docketNumber"),
                "snippet": snippet,
            },
        )

    @staticmethod
    def _build_url(absolute_url: str) -> str:
        if not absolute_url:
            return SITE_BASE
        if absolute_url.startswith("http"):
            return absolute_url
        if not absolute_url.startswith("/"):
            absolute_url = "/" + absolute_url
        return SITE_BASE + absolute_url

    @staticmethod
    def _format_judges(value: object) -> str | None:
        """CourtListener `judge` is a single string with semicolon-separated panel members."""
        if not isinstance(value, str):
            return None
        judges = [j.strip() for j in value.split(";") if j.strip()]
        return format_authors_etal(judges)

    @staticmethod
    def _coerce_str(value: object) -> str | None:
        if value is None:
            return None
        s = str(value).strip()
        return s or None
