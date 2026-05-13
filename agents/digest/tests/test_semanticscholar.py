"""Unit tests for the Semantic Scholar adapter.

No mocks. Tests build Items directly from synthetic dicts that mirror the
shape of /paper/search?fields=... responses. Shape verified against real
responses on 2026-05-13.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from digest.adapters._helpers import cutoff_datetime, parse_date_utc
from digest.adapters.semanticscholar import SemanticScholarAdapter
from digest.credibility import _per_item_bonus, source_tier, Tier


def _adapter() -> SemanticScholarAdapter:
    return SemanticScholarAdapter()


def _paper(**overrides) -> dict:
    """Minimal /paper/search-shape dict, overridable per test."""
    base = {
        "paperId": "00003fcde1fe3c572d2b4e4c704856bdbf8e7085",
        "title": "AIMC-Spec: A Benchmark Dataset for Automatic Intrapulse Modulation Classification",
        "year": 2026,
        "publicationDate": "2026-01-13",
        "citationCount": 1,
        "influentialCitationCount": 0,
        "authors": [
            {"authorId": "2399373316", "name": "Sebastian L. Cocks"},
            {"authorId": "2399367772", "name": "Salvador Dreo"},
            {"authorId": "1757942", "name": "Feras Dayoub"},
        ],
        "externalIds": {
            "DBLP": "journals/access/CocksDD25",
            "ArXiv": "2601.08265",
            "DOI": "10.1109/ACCESS.2025.3645091",
            "CorpusId": 283964494,
        },
        "venue": "IEEE Access",
        "url": "https://www.semanticscholar.org/paper/00003fcde1fe3c572d2b4e4c704856bdbf8e7085",
        "openAccessPdf": {"url": "", "status": None, "license": None},
        "tldr": None,
    }
    base.update(overrides)
    return base


def test_adapter_name():
    assert _adapter().name == "semanticscholar"


def test_engagement_combines_citation_and_influential():
    item = _adapter()._build_item(_paper(citationCount=20, influentialCitationCount=3), None)
    # 20 + 3*5 = 35
    assert item.engagement == 35


def test_engagement_zero_when_uncited():
    item = _adapter()._build_item(_paper(citationCount=0, influentialCitationCount=0), None)
    assert item.engagement == 0


def test_engagement_handles_string_counts():
    item = _adapter()._build_item(
        _paper(citationCount="100", influentialCitationCount="2"),
        None,
    )
    # 100 + 2*5 = 110
    assert item.engagement == 110


def test_engagement_handles_null_counts():
    item = _adapter()._build_item(_paper(citationCount=None, influentialCitationCount=None), None)
    assert item.engagement == 0


def test_summary_is_tldr_text():
    item = _adapter()._build_item(
        _paper(tldr={"model": "tldr@v2.0.0", "text": "This paper introduces a new dataset."}),
        None,
    )
    assert item.summary == "This paper introduces a new dataset."


def test_summary_none_when_tldr_null():
    item = _adapter()._build_item(_paper(tldr=None), None)
    assert item.summary is None


def test_summary_none_when_tldr_empty_text():
    item = _adapter()._build_item(_paper(tldr={"model": "x", "text": ""}), None)
    assert item.summary is None


def test_summary_accepts_string_tldr():
    """Forward-compat in case API ever returns a flat string."""
    item = _adapter()._build_item(_paper(tldr="Direct string summary."), None)
    assert item.summary == "Direct string summary."


def test_url_prefers_paper_url_field():
    item = _adapter()._build_item(
        _paper(url="https://www.semanticscholar.org/paper/abc123"),
        None,
    )
    assert item.url == "https://www.semanticscholar.org/paper/abc123"


def test_url_falls_back_to_paper_id():
    item = _adapter()._build_item(_paper(url=None), None)
    assert item.url.endswith("/" + _paper()["paperId"])


def test_author_format_multi():
    item = _adapter()._build_item(_paper(), None)
    assert item.author == "Sebastian L. Cocks et al."


def test_author_format_single():
    item = _adapter()._build_item(
        _paper(authors=[{"authorId": "1", "name": "Solo Author"}]),
        None,
    )
    assert item.author == "Solo Author"


def test_author_none_when_no_authors():
    item = _adapter()._build_item(_paper(authors=[]), None)
    assert item.author is None


def test_open_access_url_extracted():
    item = _adapter()._build_item(
        _paper(openAccessPdf={"url": "https://arxiv.org/pdf/2601.08265.pdf", "status": "GREEN", "license": "CC-BY"}),
        None,
    )
    assert item.raw["openAccessPdf"] == "https://arxiv.org/pdf/2601.08265.pdf"


def test_open_access_url_none_when_empty_string():
    """Real API often returns {url: '', status: None} for closed-access papers."""
    item = _adapter()._build_item(_paper(), None)
    assert item.raw["openAccessPdf"] is None


def test_open_access_url_none_when_missing():
    item = _adapter()._build_item(_paper(openAccessPdf=None), None)
    assert item.raw["openAccessPdf"] is None


def test_raw_preserves_externalids():
    item = _adapter()._build_item(_paper(), None)
    assert item.raw["externalIds"]["ArXiv"] == "2601.08265"
    assert item.raw["externalIds"]["DOI"] == "10.1109/ACCESS.2025.3645091"


def test_raw_preserves_venue_and_year():
    item = _adapter()._build_item(_paper(), None)
    assert item.raw["venue"] == "IEEE Access"
    assert item.raw["year"] == 2026


def test_timestamp_from_publication_date():
    item = _adapter()._build_item(
        _paper(publicationDate="2024-06-15"),
        parse_date_utc("2024-06-15"),
    )
    assert item.timestamp.year == 2024
    assert item.timestamp.month == 6
    assert item.timestamp.day == 15
    assert item.timestamp.tzinfo == timezone.utc


def test_timestamp_falls_back_to_year_midpoint():
    """When publicationDate is missing, use July 1 of the year as a proxy."""
    item = _adapter()._build_item(
        _paper(publicationDate=None, year=2020),
        None,
    )
    assert item.timestamp.year == 2020
    assert item.timestamp.month == 7


def test_timestamp_falls_back_to_now_when_no_date_or_year():
    item = _adapter()._build_item(_paper(publicationDate=None, year=None), None)
    assert item.timestamp is not None


def test_parse_pubdate_returns_none_for_bad_string():
    """S2 uses the shared `parse_date_utc` helper."""
    assert parse_date_utc("not-a-date") is None


def test_parse_pubdate_returns_none_for_none():
    assert parse_date_utc(None) is None


def test_source_tier_is_deliberate():
    assert source_tier("semanticscholar") == Tier.DELIBERATE


def test_per_item_bonus_high_influential():
    assert _per_item_bonus("semanticscholar", {"influentialCitationCount": 100}) == 0.4


def test_per_item_bonus_medium_influential():
    assert _per_item_bonus("semanticscholar", {"influentialCitationCount": 25}) == 0.2


def test_per_item_bonus_zero_low_influential():
    assert _per_item_bonus("semanticscholar", {"influentialCitationCount": 5}) == 0.0


def test_per_item_bonus_zero_when_field_missing():
    assert _per_item_bonus("semanticscholar", {}) == 0.0


def test_title_falls_back_to_paper_id():
    item = _adapter()._build_item(_paper(title=None), None)
    assert item.title == _paper()["paperId"]


def test_cutoff_filters_old_papers_in_fetch_logic():
    """S2 uses `cutoff_datetime` from helpers for client-side date filtering."""
    cutoff = cutoff_datetime(30)
    assert cutoff is not None

    old_date = parse_date_utc("2010-01-01")
    fresh_date = datetime.now(timezone.utc) - timedelta(days=5)

    assert old_date < cutoff
    assert fresh_date > cutoff


def test_cutoff_none_when_days_zero():
    assert cutoff_datetime(0) is None


def test_adapter_registered():
    from digest.adapters import ADAPTERS, get_adapter

    assert "semanticscholar" in ADAPTERS
    adapter = get_adapter("semanticscholar")
    assert adapter.name == "semanticscholar"
