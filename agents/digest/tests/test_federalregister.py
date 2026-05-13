"""Unit tests for the Federal Register adapter.

No mocks. Tests build Items directly from synthetic dicts that mirror the
shape of federalregister.gov's /documents.json response. The shape comes
from real responses to /api/v1/documents.json -- see the SPECS.md note
about why `comment_count` is not used.
"""

from __future__ import annotations

from datetime import timezone

from digest.adapters._helpers import since_date
from digest.adapters.federalregister import FederalRegisterAdapter
from digest.credibility import _per_item_bonus, source_tier, Tier


def _adapter() -> FederalRegisterAdapter:
    return FederalRegisterAdapter()


def test_adapter_name():
    assert _adapter().name == "federalregister"


def test_engagement_uses_page_views_count():
    doc = {
        "title": "Some Rule",
        "document_number": "2024-12345",
        "page_views": {"count": 1981, "last_updated": "2026-05-13 10:15:06 -0400"},
        "significant": None,
        "publication_date": "2024-06-01",
        "html_url": "https://www.federalregister.gov/d/2024-12345",
    }
    item = _adapter()._build_item(doc)
    assert item.engagement == 1981


def test_engagement_adds_significant_bonus():
    doc = {
        "title": "Significant Rule",
        "document_number": "2024-12346",
        "page_views": {"count": 100},
        "significant": True,
        "publication_date": "2024-06-01",
        "html_url": "https://www.federalregister.gov/d/2024-12346",
    }
    item = _adapter()._build_item(doc)
    # 100 page views + 50 significant bonus
    assert item.engagement == 150


def test_engagement_zero_when_no_views_and_not_significant():
    doc = {
        "title": "Quiet Notice",
        "document_number": "2024-12347",
        "significant": None,
        "publication_date": "2024-06-01",
        "html_url": "https://www.federalregister.gov/d/2024-12347",
    }
    item = _adapter()._build_item(doc)
    assert item.engagement == 0


def test_engagement_handles_raw_int_page_views():
    """Forward-compat: API currently returns dict, but accept ints too."""
    doc = {
        "title": "Rule",
        "document_number": "2024-12348",
        "page_views": 500,
        "significant": False,
        "publication_date": "2024-06-01",
        "html_url": "https://www.federalregister.gov/d/2024-12348",
    }
    item = _adapter()._build_item(doc)
    assert item.engagement == 500


def test_engagement_handles_invalid_page_views():
    doc = {
        "title": "Rule",
        "document_number": "2024-12349",
        "page_views": "not-a-number",
        "significant": False,
        "publication_date": "2024-06-01",
        "html_url": "https://www.federalregister.gov/d/2024-12349",
    }
    item = _adapter()._build_item(doc)
    assert item.engagement == 0


def test_engagement_handles_null_count_in_page_views():
    doc = {
        "title": "Rule",
        "document_number": "2024-12349a",
        "page_views": {"count": None, "last_updated": None},
        "significant": False,
        "publication_date": "2024-06-01",
        "html_url": "https://www.federalregister.gov/d/2024-12349a",
    }
    item = _adapter()._build_item(doc)
    assert item.engagement == 0


def test_author_is_first_agency_name():
    doc = {
        "title": "EPA Rule",
        "document_number": "2024-12350",
        "agencies": [
            {"name": "Environmental Protection Agency", "raw_name": "EPA"},
            {"name": "Department of Energy"},
        ],
        "publication_date": "2024-06-01",
        "html_url": "https://www.federalregister.gov/d/2024-12350",
    }
    item = _adapter()._build_item(doc)
    assert item.author == "Environmental Protection Agency"


def test_author_falls_back_to_raw_name():
    doc = {
        "title": "Rule",
        "document_number": "2024-12351",
        "agencies": [{"raw_name": "Some New Agency"}],
        "publication_date": "2024-06-01",
        "html_url": "https://www.federalregister.gov/d/2024-12351",
    }
    item = _adapter()._build_item(doc)
    assert item.author == "Some New Agency"


def test_author_none_when_no_agencies():
    doc = {
        "title": "Rule",
        "document_number": "2024-12352",
        "publication_date": "2024-06-01",
        "html_url": "https://www.federalregister.gov/d/2024-12352",
    }
    item = _adapter()._build_item(doc)
    assert item.author is None


def test_raw_preserves_signals():
    doc = {
        "title": "Big Rule",
        "document_number": "2024-12353",
        "type": "Proposed Rule",
        "page_views": {"count": 5000, "last_updated": "2026-05-13 10:15:06 -0400"},
        "significant": True,
        "abstract": "A summary of the rule.",
        "comments_close_on": "2024-08-01",
        "agencies": [{"name": "FDA"}],
        "publication_date": "2024-06-01",
        "html_url": "https://www.federalregister.gov/d/2024-12353",
        "regulations_dot_gov_url": "https://www.regulations.gov/docket/FDA-2024-N-0001",
    }
    item = _adapter()._build_item(doc)
    assert item.raw["document_number"] == "2024-12353"
    assert item.raw["type"] == "Proposed Rule"
    assert item.raw["page_views"] == 5000
    assert item.raw["significant"] is True
    assert item.raw["agencies"] == ["FDA"]
    assert item.raw["comments_close_on"] == "2024-08-01"
    assert item.raw["regulations_dot_gov_url"].endswith("FDA-2024-N-0001")


def test_summary_uses_abstract():
    doc = {
        "title": "Rule",
        "document_number": "2024-12354",
        "abstract": "This rule establishes new requirements.",
        "publication_date": "2024-06-01",
        "html_url": "https://www.federalregister.gov/d/2024-12354",
    }
    item = _adapter()._build_item(doc)
    assert item.summary == "This rule establishes new requirements."


def test_url_falls_back_when_missing():
    doc = {
        "title": "Rule",
        "document_number": "2024-12355",
        "publication_date": "2024-06-01",
    }
    item = _adapter()._build_item(doc)
    assert item.url == "https://www.federalregister.gov/"


def test_publication_date_parses_to_utc():
    doc = {
        "title": "Rule",
        "document_number": "2024-12356",
        "publication_date": "2024-03-15",
        "html_url": "https://www.federalregister.gov/d/2024-12356",
    }
    item = _adapter()._build_item(doc)
    assert item.timestamp.year == 2024
    assert item.timestamp.month == 3
    assert item.timestamp.day == 15
    assert item.timestamp.tzinfo == timezone.utc


def test_publication_date_fallback_to_now_when_missing():
    doc = {
        "title": "Rule",
        "document_number": "2024-12357",
        "html_url": "https://www.federalregister.gov/d/2024-12357",
    }
    item = _adapter()._build_item(doc)
    assert item.timestamp is not None


def test_agencies_list_filters_empty():
    doc = {
        "title": "Rule",
        "document_number": "2024-12358",
        "agencies": [{}, {"name": "Real Agency"}, None],
        "publication_date": "2024-06-01",
        "html_url": "https://www.federalregister.gov/d/2024-12358",
    }
    item = _adapter()._build_item(doc)
    assert item.raw["agencies"] == ["Real Agency"]


def test_source_tier_is_verified():
    assert source_tier("federalregister") == Tier.VERIFIED


def test_per_item_bonus_significant_only():
    raw = {"page_views": 0, "significant": True}
    assert _per_item_bonus("federalregister", raw) == 0.3


def test_per_item_bonus_high_page_views_only():
    raw = {"page_views": 15000, "significant": False}
    assert _per_item_bonus("federalregister", raw) == 0.4


def test_per_item_bonus_medium_page_views_only():
    raw = {"page_views": 2500, "significant": False}
    assert _per_item_bonus("federalregister", raw) == 0.2


def test_per_item_bonus_caps_at_half():
    raw = {"page_views": 50000, "significant": True}
    # 0.3 + 0.4 = 0.7, capped to 0.5
    assert _per_item_bonus("federalregister", raw) == 0.5


def test_per_item_bonus_zero_for_quiet_non_significant():
    raw = {"page_views": 50, "significant": False}
    assert _per_item_bonus("federalregister", raw) == 0.0


def test_since_date_helper_returns_iso_format():
    """FR uses the shared `since_date` helper; verify it's wired correctly."""
    s = since_date(30)
    assert s is not None
    assert len(s) == 10
    assert s[4] == "-"
    assert s[7] == "-"


def test_adapter_registered():
    from digest.adapters import ADAPTERS, get_adapter

    assert "federalregister" in ADAPTERS
    adapter = get_adapter("federalregister")
    assert adapter.name == "federalregister"
