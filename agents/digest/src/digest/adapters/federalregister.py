"""Federal Register adapter (federalregister.gov, no auth required).

Fetches recent rules, proposed rules, notices, and presidential documents
matching the query terms. Engagement is `page_views.count` plus a bonus when
the document is flagged "significant" under Executive Order 12866.

Note: the SPECS.md draft for this adapter listed `comment_count` as a valid
field on the list endpoint. It is not. `comment_count` only exists on the
per-document detail endpoint, nested under `dockets[].documents[]`. The list
endpoint returns 400 if you request it. We use `page_views.count` instead --
noisier but available without a second API call. If a future iteration wants
deliberate (not passive) engagement, do a per-item detail fetch and read
`dockets[0].documents[0].comment_count`.
"""

from __future__ import annotations

from datetime import datetime, timezone

from digest.adapters._helpers import coerce_int, fetch_json, parse_iso_utc, since_date
from digest.expansion import ExpandedQuery
from digest.models import Item

API_URL = "https://www.federalregister.gov/api/v1/documents.json"

FIELDS = [
    "title",
    "abstract",
    "document_number",
    "type",
    "agencies",
    "publication_date",
    "page_views",
    "significant",
    "comments_close_on",
    "html_url",
    "regulations_dot_gov_url",
]

# Bonus added to engagement (page_views) when the rule is flagged as
# significant under EO 12866.
SIGNIFICANT_ENGAGEMENT_BONUS = 50


class FederalRegisterAdapter:
    name = "federalregister"

    def fetch(self, query: ExpandedQuery, days: int, limit: int = 50) -> list[Item]:
        """Fetch recent federal register documents matching any query term.

        Runs one request per term (the API takes a single `conditions[term]`,
        not a list), dedupes by document_number, and returns up to `limit`
        items in publication-date order (newest first).
        """
        since = since_date(days) or datetime.now(timezone.utc).date().isoformat()
        seen: dict[str, Item] = {}

        for term in query.terms:
            for doc in self._fetch_term(term, since, limit):
                key = doc.get("document_number")
                if not key or key in seen:
                    continue
                seen[key] = self._build_item(doc)
                if len(seen) >= limit:
                    return list(seen.values())

        return list(seen.values())[:limit]

    def _fetch_term(self, term: str, since: str, limit: int) -> list[dict]:
        params: list[tuple[str, str]] = [
            ("conditions[term]", term),
            ("conditions[publication_date][gte]", since),
            ("per_page", str(min(limit, 100))),
            ("order", "newest"),
        ]
        params.extend(("fields[]", field) for field in FIELDS)
        payload = fetch_json(API_URL, params=params, default={})
        return payload.get("results", []) or []

    def _build_item(self, doc: dict) -> Item:
        page_views = self._page_views_count(doc.get("page_views"))
        significant = bool(doc.get("significant"))
        engagement = page_views + (SIGNIFICANT_ENGAGEMENT_BONUS if significant else 0)

        agencies = doc.get("agencies") or []
        agency_name = self._first_agency_name(agencies)
        author = agency_name if agency_name else None

        title = doc.get("title") or doc.get("document_number") or "Federal Register document"
        url = doc.get("html_url") or "https://www.federalregister.gov/"

        timestamp = parse_iso_utc(doc.get("publication_date")) or datetime.now(timezone.utc)

        return Item(
            source=self.name,
            title=title,
            url=url,
            author=author,
            timestamp=timestamp,
            engagement=engagement,
            summary=doc.get("abstract"),
            raw={
                "document_number": doc.get("document_number"),
                "type": doc.get("type"),
                "page_views": page_views,
                "significant": significant,
                "agencies": [self._agency_name(a) for a in agencies if a],
                "abstract": doc.get("abstract"),
                "comments_close_on": doc.get("comments_close_on"),
                "regulations_dot_gov_url": doc.get("regulations_dot_gov_url"),
            },
        )

    @staticmethod
    def _page_views_count(value: object) -> int:
        """Extract the count from the API's `page_views` object: `{count, last_updated}`.

        Accepts a raw int as well, for forward-compatibility and easy testing.
        """
        if isinstance(value, dict):
            return coerce_int(value.get("count"))
        return coerce_int(value)

    @staticmethod
    def _agency_name(agency: object) -> str:
        if isinstance(agency, dict):
            return agency.get("name") or agency.get("raw_name") or ""
        if isinstance(agency, str):
            return agency
        return ""

    @classmethod
    def _first_agency_name(cls, agencies: list) -> str:
        for agency in agencies:
            name = cls._agency_name(agency)
            if name:
                return name
        return ""

