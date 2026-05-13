"""OpenAlex adapter (api.openalex.org/works, key optional).

Single-step `/works` search per term. Returns up to `limit` results across
all terms, deduped by OpenAlex work ID (e.g. `W1234567890`).

Auth precedence:
  1. `OPENALEX_API_KEY` -- passed as `api_key` query param
  2. `OPENALEX_EMAIL` -- passed as `mailto` query param (polite pool)
  3. Anonymous -- still works, lower rate limit

Engagement is `cited_by_count`. Per-item bonus uses `fwci` (field-weighted
citation impact, where 1.0 = field average). `fwci` is `None` for too-new
papers; preserve as `None` in raw rather than coercing to 0 so the bonus
function can distinguish "no citations yet" from "below field average."
"""

from __future__ import annotations

import os
import re
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

API_URL = "https://api.openalex.org/works"

# Fields we ask /works to return. Keeping this list narrow keeps responses
# small (OpenAlex defaults to ALL fields, which is ~30KB per item).
SELECT_FIELDS = ",".join([
    "id",
    "doi",
    "title",
    "cited_by_count",
    "counts_by_year",
    "fwci",
    "type",
    "open_access",
    "authorships",
    "publication_date",
    "concepts",
])

# Matches OpenAlex IDs like W1234567890 in URLs like https://openalex.org/W1234567890
WORK_ID_RE = re.compile(r"openalex\.org/(W\d+)")


class OpenAlexAdapter:
    name = "openalex"

    def __init__(self) -> None:
        self._api_key = os.environ.get("OPENALEX_API_KEY", "")
        self._email = os.environ.get("OPENALEX_EMAIL", "")

    def fetch(self, query: ExpandedQuery, days: int, limit: int = 50) -> list[Item]:
        """Fetch recent OpenAlex works matching any query term.

        One /works search per term. Dedupes by work ID. Returns up to `limit`
        items sorted by publication date (newest first). Uses native
        `from_publication_date` filter when `days > 0`.
        """
        since = since_date(days)
        seen: dict[str, Item] = {}

        for term in query.terms:
            for work in self._search(term, since, limit):
                work_id = self._extract_work_id(work)
                if not work_id or work_id in seen:
                    continue
                seen[work_id] = self._build_item(work, work_id)
                if len(seen) >= limit:
                    return list(seen.values())

        return list(seen.values())[:limit]

    def _search(self, term: str, since: str | None, limit: int) -> list[dict]:
        params: dict[str, str] = {
            "search": term,
            "sort": "publication_date:desc",
            "per_page": str(min(limit, 200)),
            "select": SELECT_FIELDS,
        }
        if since:
            params["filter"] = f"from_publication_date:{since}"
        if self._api_key:
            params["api_key"] = self._api_key
        elif self._email:
            params["mailto"] = self._email

        payload = fetch_json(API_URL, params=params, default={})
        return payload.get("results", []) or []

    def _build_item(self, work: dict, work_id: str) -> Item:
        title = work.get("title") or work_id
        doi = self._normalize_doi(work.get("doi"))

        # Prefer the DOI URL (more durable) over the OpenAlex page.
        url = doi or work.get("id") or f"https://openalex.org/{work_id}"

        cited_by_count = coerce_int(work.get("cited_by_count"))
        fwci = coerce_float(work.get("fwci"))
        open_access = work.get("open_access") or {}
        oa_url = open_access.get("oa_url") or None
        is_oa = bool(open_access.get("is_oa"))

        authorships = work.get("authorships") or []
        author = format_authors_etal(self._extract_author_names(authorships))

        pub_date = parse_date_utc(work.get("publication_date"))
        timestamp = pub_date or datetime.now(timezone.utc)

        concepts = [
            {
                "id": self._tail_id(c.get("id")),
                "display_name": c.get("display_name"),
                "level": c.get("level"),
                "score": c.get("score"),
            }
            for c in (work.get("concepts") or [])
            if isinstance(c, dict)
        ]

        return Item(
            source=self.name,
            title=title,
            url=url,
            author=author,
            timestamp=timestamp,
            engagement=cited_by_count,
            summary=None,  # OpenAlex doesn't return abstract by default
            raw={
                "id": work_id,
                "doi": doi,
                "cited_by_count": cited_by_count,
                "counts_by_year": work.get("counts_by_year") or [],
                "fwci": fwci,
                "type": work.get("type"),
                "open_access": {
                    "is_oa": is_oa,
                    "oa_url": oa_url,
                    "oa_status": open_access.get("oa_status"),
                },
                "concepts": concepts,
            },
        )

    @staticmethod
    def _extract_work_id(work: dict) -> str | None:
        """Pull 'W1234567890' out of 'https://openalex.org/W1234567890'."""
        wid = work.get("id")
        if not wid or not isinstance(wid, str):
            return None
        match = WORK_ID_RE.search(wid)
        return match.group(1) if match else None

    @staticmethod
    def _normalize_doi(value: object) -> str | None:
        """OpenAlex returns DOIs as full URLs like 'https://doi.org/10.1234/...'.

        Return as-is if it's already a URL, or wrap a bare DOI in https://doi.org/.
        Return None when missing.
        """
        if not value or not isinstance(value, str):
            return None
        if value.startswith("http"):
            return value
        return f"https://doi.org/{value}"

    @staticmethod
    def _extract_author_names(authorships: list) -> list[str]:
        """Pull display_names (or raw_author_name fallback) from /works authorships."""
        names: list[str] = []
        for entry in authorships:
            if not isinstance(entry, dict):
                continue
            author = entry.get("author") or {}
            name = author.get("display_name") or entry.get("raw_author_name")
            if name:
                names.append(name)
        return names

    @staticmethod
    def _tail_id(value: object) -> str | None:
        """OpenAlex IDs are URLs; return just the trailing segment."""
        if not value or not isinstance(value, str):
            return None
        return value.rsplit("/", 1)[-1] or None

