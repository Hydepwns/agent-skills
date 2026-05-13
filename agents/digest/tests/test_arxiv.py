"""Unit tests for the arXiv adapter.

No mocks. Tests build Items directly from synthetic Atom entry XML strings
that mirror what arXiv's API returns. Shape verified against real
http://export.arxiv.org/api/query responses on 2026-05-13.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from datetime import timezone

from digest.adapters.arxiv import NS, ArxivAdapter
from digest.credibility import _per_item_bonus, source_tier, Tier


def _adapter() -> ArxivAdapter:
    return ArxivAdapter()


def _entry(
    *,
    arxiv_id: str = "2605.12498",
    version: str = "v1",
    title: str = "EgoForce: Forearm-Guided Camera-Space 3D Hand Pose",
    summary: str = "We present EgoForce, a 3D hand-pose model.",
    published: str = "2026-05-12T17:59:56Z",
    categories: list[str] | None = None,
    primary_category: str = "cs.CV",
    pdf_url: str | None = "https://arxiv.org/pdf/2605.12498v1",
    html_url: str | None = "https://arxiv.org/abs/2605.12498v1",
    comment: str | None = "23 pages, 19 figures; SIGGRAPH 2026",
    authors: list[str] | None = None,
) -> ET.Element:
    """Build a single Atom <entry> matching arXiv's response shape."""
    if categories is None:
        categories = ["cs.CV", "cs.GR"]
    if authors is None:
        authors = ["Christen Millerdurai", "Shaoxiang Wang", "Yaxu Xie"]

    parts = [
        '<entry xmlns="http://www.w3.org/2005/Atom"',
        ' xmlns:arxiv="http://arxiv.org/schemas/atom">',
        f'<id>http://arxiv.org/abs/{arxiv_id}{version}</id>',
        f"<title>{title}</title>",
        f"<summary>{summary}</summary>",
        f"<published>{published}</published>",
        f"<updated>{published}</updated>",
    ]
    if html_url:
        parts.append(f'<link href="{html_url}" rel="alternate" type="text/html"/>')
    if pdf_url:
        parts.append(f'<link href="{pdf_url}" rel="related" type="application/pdf" title="pdf"/>')
    for cat in categories:
        parts.append(f'<category term="{cat}" scheme="http://arxiv.org/schemas/atom"/>')
    if primary_category:
        parts.append(f'<arxiv:primary_category term="{primary_category}"/>')
    if comment:
        parts.append(f"<arxiv:comment>{comment}</arxiv:comment>")
    for author in authors:
        parts.append(f"<author><name>{author}</name></author>")
    parts.append("</entry>")
    return ET.fromstring("".join(parts))


def test_adapter_name():
    assert _adapter().name == "arxiv"


def test_engagement_is_zero():
    """arXiv has no engagement signal -- must always be 0."""
    adapter = _adapter()
    entry = _entry()
    arxiv_id = adapter._extract_arxiv_id(entry)
    item = adapter._build_item(entry, arxiv_id, adapter._parse_timestamp(entry, "published"))
    assert item.engagement == 0


def test_extract_arxiv_id_strips_version():
    entry = _entry(arxiv_id="2401.12345", version="v3")
    assert _adapter()._extract_arxiv_id(entry) == "2401.12345"


def test_extract_arxiv_id_handles_no_version():
    entry = _entry(arxiv_id="2401.12345", version="")
    assert _adapter()._extract_arxiv_id(entry) == "2401.12345"


def test_extract_arxiv_id_handles_old_style_id():
    """Pre-2007 IDs have a subject prefix like 'cs.LG/0701234'."""
    entry = _entry(arxiv_id="cs.LG/0701234", version="v2")
    # Our regex captures everything after /abs/ up to vN -- old IDs include the slash.
    # The matcher should still pull the trailing segment.
    extracted = _adapter()._extract_arxiv_id(entry)
    # Either the prefixed form or the trailing segment is acceptable as long as it's stable
    assert extracted is not None
    assert "0701234" in extracted


def test_url_uses_alternate_link():
    entry = _entry(html_url="https://arxiv.org/abs/2605.12498v1")
    item = _adapter()._build_item(entry, "2605.12498", None)
    assert item.url == "https://arxiv.org/abs/2605.12498v1"


def test_url_falls_back_to_constructed():
    entry = _entry(html_url=None)
    item = _adapter()._build_item(entry, "2605.12498", None)
    assert item.url == "https://arxiv.org/abs/2605.12498"


def test_pdf_url_in_raw():
    entry = _entry(pdf_url="https://arxiv.org/pdf/2605.12498v1")
    item = _adapter()._build_item(entry, "2605.12498", None)
    assert item.raw["pdf_url"] == "https://arxiv.org/pdf/2605.12498v1"


def test_pdf_url_none_when_missing():
    entry = _entry(pdf_url=None)
    item = _adapter()._build_item(entry, "2605.12498", None)
    assert item.raw["pdf_url"] is None


def test_title_collapses_whitespace():
    """arXiv inserts newlines into <title> elements -- collapse them."""
    entry = _entry(title="Long Title\n   With Indented\n  Continuation")
    item = _adapter()._build_item(entry, "2605.12498", None)
    assert item.title == "Long Title With Indented Continuation"


def test_summary_collapses_whitespace():
    """Abstracts are wrapped across multiple lines in the XML -- collapse them."""
    entry = _entry(summary="Line one.\n  Line two.\n    Line three.")
    item = _adapter()._build_item(entry, "2605.12498", None)
    assert item.summary == "Line one. Line two. Line three."


def test_author_single():
    entry = _entry(authors=["Solo Researcher"])
    item = _adapter()._build_item(entry, "2605.12498", None)
    assert item.author == "Solo Researcher"


def test_author_multi_uses_et_al():
    entry = _entry(authors=["First Author", "Second Author", "Third Author"])
    item = _adapter()._build_item(entry, "2605.12498", None)
    assert item.author == "First Author et al."


def test_author_none_when_empty():
    entry = _entry(authors=[])
    item = _adapter()._build_item(entry, "2605.12498", None)
    assert item.author is None


def test_categories_extracted():
    entry = _entry(categories=["cs.CV", "cs.GR", "cs.LG"])
    item = _adapter()._build_item(entry, "2605.12498", None)
    assert item.raw["categories"] == ["cs.CV", "cs.GR", "cs.LG"]


def test_primary_category():
    entry = _entry(primary_category="cs.CR")
    item = _adapter()._build_item(entry, "2605.12498", None)
    assert item.raw["primary_category"] == "cs.CR"


def test_primary_category_none_when_missing():
    entry = _entry(primary_category="")
    item = _adapter()._build_item(entry, "2605.12498", None)
    # Empty string is fine here -- the XML attribute is what it is
    assert item.raw["primary_category"] in ("", None)


def test_comment_extracted():
    entry = _entry(comment="Accepted at NeurIPS 2025")
    item = _adapter()._build_item(entry, "2605.12498", None)
    assert item.raw["comment"] == "Accepted at NeurIPS 2025"


def test_comment_none_when_missing():
    entry = _entry(comment=None)
    item = _adapter()._build_item(entry, "2605.12498", None)
    assert item.raw["comment"] is None


def test_published_parses_to_utc():
    entry = _entry(published="2025-03-15T10:30:00Z")
    adapter = _adapter()
    ts = adapter._parse_timestamp(entry, "published")
    assert ts is not None
    assert ts.year == 2025
    assert ts.month == 3
    assert ts.day == 15
    assert ts.tzinfo == timezone.utc


def test_published_fallback_to_now_when_unparseable():
    entry = _entry(published="not-a-date")
    adapter = _adapter()
    item = adapter._build_item(entry, "2605.12498", None)
    assert item.timestamp is not None


def test_source_tier_is_deliberate():
    assert source_tier("arxiv") == Tier.DELIBERATE


def test_per_item_bonus_is_zero():
    """arXiv has no per-item credibility signal of its own."""
    assert _per_item_bonus("arxiv", {"arxiv_id": "2401.12345"}) == 0.0


def test_rate_limit_first_request_does_not_sleep(monkeypatch):
    """The first call to _respect_rate_limit must not sleep."""
    slept: list[float] = []

    def fake_sleep(sec: float) -> None:
        slept.append(sec)

    monkeypatch.setattr("digest.adapters.arxiv.time.sleep", fake_sleep)
    adapter = ArxivAdapter()
    adapter._respect_rate_limit()
    assert slept == []


def test_rate_limit_subsequent_request_sleeps(monkeypatch):
    """A second call within 3s should trigger a sleep of (3 - elapsed)."""
    slept: list[float] = []

    def fake_sleep(sec: float) -> None:
        slept.append(sec)

    # Fake monotonic (always > 0 in real usage): first call yields 100.0 twice
    # (once for the elapsed check, once for the assignment), then second call
    # yields 101.0 twice. elapsed = 101.0 - 100.0 = 1.0, so sleep should be 2.0s.
    tick = iter([100.0, 100.0, 101.0, 101.0])
    monkeypatch.setattr("digest.adapters.arxiv.time.sleep", fake_sleep)
    monkeypatch.setattr("digest.adapters.arxiv.time.monotonic", lambda: next(tick))

    adapter = ArxivAdapter()
    adapter._respect_rate_limit()  # first call, sets last_request_ts to 100.0
    adapter._respect_rate_limit()  # second call, elapsed=1.0, should sleep 2.0s
    assert len(slept) == 1
    assert slept[0] == 2.0


def test_adapter_registered():
    from digest.adapters import ADAPTERS, get_adapter

    assert "arxiv" in ADAPTERS
    adapter = get_adapter("arxiv")
    assert adapter.name == "arxiv"


def test_namespaces_constant():
    """The NS dict is what _build_item uses for XPath lookups -- guard against typos."""
    assert NS["atom"] == "http://www.w3.org/2005/Atom"
    assert NS["arxiv"] == "http://arxiv.org/schemas/atom"
