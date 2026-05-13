"""arXiv adapter (export.arxiv.org/api/query, no auth).

Atom XML feed parsed with stdlib `xml.etree.ElementTree`. One search per
query term, dedupe by versionless arxiv_id (e.g. `2401.12345`).

arXiv provides no engagement signal (no views, downloads, or citations), so
`Item.engagement` is set to 0. Recency-based ranking carries the score.
A future enhancement could batch-enrich via Semantic Scholar `/paper/arXiv:{id}`
to inject citation counts, but that's a composite-mode wiring change and
lives outside this adapter.

Rate limit: arXiv enforces 1 request per 3 seconds, hard-checked at the
server. The adapter sleeps 3 seconds between term searches (skipping the
sleep on the first request).
"""

from __future__ import annotations

import re
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timezone

from digest.adapters._helpers import (
    cutoff_datetime,
    fetch_text,
    format_authors_etal,
    parse_iso_utc,
)
from digest.expansion import ExpandedQuery
from digest.models import Item

API_URL = "http://export.arxiv.org/api/query"

NS = {
    "atom": "http://www.w3.org/2005/Atom",
    "opensearch": "http://a9.com/-/spec/opensearch/1.1/",
    "arxiv": "http://arxiv.org/schemas/atom",
}

# Matches modern IDs like '/abs/2401.12345v1' and pre-2007 IDs like '/abs/cs.LG/0701234v2'.
ARXIV_ID_RE = re.compile(r"/abs/(.+?)(?:v\d+)?$")

RATE_LIMIT_SECONDS = 3.0


class ArxivAdapter:
    name = "arxiv"

    def __init__(self) -> None:
        self._last_request_ts: float = 0.0

    def fetch(self, query: ExpandedQuery, days: int, limit: int = 50) -> list[Item]:
        """Fetch recent arXiv papers matching any query term.

        One search per term (sequential with 3s rate-limit sleep). Dedupes by
        versionless arxiv_id. Client-side filters by `published` against the
        `days` window since the API has no native publication-date filter.
        """
        cutoff = cutoff_datetime(days)
        seen: dict[str, Item] = {}

        for term in query.terms:
            entries = self._search(term, limit)
            for entry in entries:
                arxiv_id = self._extract_arxiv_id(entry)
                if not arxiv_id or arxiv_id in seen:
                    continue
                published = self._parse_timestamp(entry, "published")
                if cutoff and published and published < cutoff:
                    continue
                seen[arxiv_id] = self._build_item(entry, arxiv_id, published)
                if len(seen) >= limit:
                    return list(seen.values())

        return list(seen.values())[:limit]

    def _search(self, term: str, limit: int) -> list[ET.Element]:
        self._respect_rate_limit()
        params = {
            "search_query": f'all:"{term}"',
            "start": "0",
            "max_results": str(min(limit, 100)),
            "sortBy": "submittedDate",
            "sortOrder": "descending",
        }
        body = fetch_text(API_URL, params=params, follow_redirects=True)
        if not body:
            return []
        try:
            root = ET.fromstring(body)
        except ET.ParseError:
            return []
        return root.findall("atom:entry", NS)

    def _respect_rate_limit(self) -> None:
        """Sleep so consecutive requests are at least RATE_LIMIT_SECONDS apart."""
        now = time.monotonic()
        elapsed = now - self._last_request_ts
        if self._last_request_ts > 0 and elapsed < RATE_LIMIT_SECONDS:
            time.sleep(RATE_LIMIT_SECONDS - elapsed)
        self._last_request_ts = time.monotonic()

    def _build_item(
        self,
        entry: ET.Element,
        arxiv_id: str,
        published: datetime | None,
    ) -> Item:
        title = self._text(entry, "atom:title") or arxiv_id
        title = " ".join(title.split())  # collapse the inline XML whitespace

        summary = self._text(entry, "atom:summary")
        if summary:
            summary = " ".join(summary.split())

        html_url = self._link(entry, "alternate") or f"https://arxiv.org/abs/{arxiv_id}"
        pdf_url = self._link(entry, "related", "application/pdf")

        primary_cat_el = entry.find("arxiv:primary_category", NS)
        primary_category = primary_cat_el.attrib.get("term") if primary_cat_el is not None else None

        categories = [
            cat.attrib["term"]
            for cat in entry.findall("atom:category", NS)
            if "term" in cat.attrib
        ]

        comment_el = entry.find("arxiv:comment", NS)
        comment = comment_el.text.strip() if comment_el is not None and comment_el.text else None

        authors = [
            (author.findtext("atom:name", default="", namespaces=NS) or "").strip()
            for author in entry.findall("atom:author", NS)
        ]

        timestamp = published or datetime.now(timezone.utc)

        return Item(
            source=self.name,
            title=title,
            url=html_url,
            author=format_authors_etal(authors),
            timestamp=timestamp,
            engagement=0,  # arXiv has no engagement signal
            summary=summary,
            raw={
                "arxiv_id": arxiv_id,
                "categories": categories,
                "primary_category": primary_category,
                "pdf_url": pdf_url,
                "authors": authors,
                "comment": comment,
            },
        )

    @staticmethod
    def _extract_arxiv_id(entry: ET.Element) -> str | None:
        """Pull '2401.12345' out of 'http://arxiv.org/abs/2401.12345v1'."""
        id_el = entry.find("atom:id", NS)
        if id_el is None or not id_el.text:
            return None
        match = ARXIV_ID_RE.search(id_el.text.strip())
        return match.group(1) if match else None

    @staticmethod
    def _text(entry: ET.Element, path: str) -> str:
        el = entry.find(path, NS)
        if el is None or el.text is None:
            return ""
        return el.text.strip()

    @staticmethod
    def _link(entry: ET.Element, rel: str, link_type: str | None = None) -> str | None:
        for link in entry.findall("atom:link", NS):
            if link.attrib.get("rel") != rel:
                continue
            if link_type and link.attrib.get("type") != link_type:
                continue
            href = link.attrib.get("href")
            if href:
                return href
        return None

    @staticmethod
    def _parse_timestamp(entry: ET.Element, tag: str) -> datetime | None:
        return parse_iso_utc(ArxivAdapter._text(entry, f"atom:{tag}"))
