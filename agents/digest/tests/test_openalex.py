"""Unit tests for the OpenAlex adapter.

No mocks. Synthetic dicts mirror the real /works response shape verified
against api.openalex.org on 2026-05-13.
"""

from __future__ import annotations

from datetime import timezone

from digest.adapters.openalex import OpenAlexAdapter
from digest.credibility import _per_item_bonus, source_tier, Tier


def _adapter() -> OpenAlexAdapter:
    return OpenAlexAdapter()


def _work(**overrides) -> dict:
    """Minimal /works result dict, overridable per test."""
    base = {
        "id": "https://openalex.org/W4400000000",
        "doi": "https://doi.org/10.1234/example.2026.001",
        "title": "A Study of mRNA Vaccine Delivery via Lipid Nanoparticles",
        "publication_date": "2026-03-15",
        "type": "article",
        "cited_by_count": 42,
        "fwci": 1.7,
        "open_access": {
            "is_oa": True,
            "oa_status": "gold",
            "oa_url": "https://example.com/paper.pdf",
            "any_repository_has_fulltext": True,
        },
        "counts_by_year": [
            {"year": 2026, "cited_by_count": 30},
            {"year": 2025, "cited_by_count": 12},
        ],
        "authorships": [
            {
                "author_position": "first",
                "author": {
                    "id": "https://openalex.org/A5001",
                    "display_name": "Jane Doe",
                    "orcid": None,
                },
                "raw_author_name": "Doe, Jane",
            },
            {
                "author_position": "middle",
                "author": {
                    "id": "https://openalex.org/A5002",
                    "display_name": "John Smith",
                },
            },
        ],
        "concepts": [
            {
                "id": "https://openalex.org/C2776760102",
                "display_name": "RNA",
                "level": 2,
                "score": 0.87,
            }
        ],
    }
    base.update(overrides)
    return base


def test_adapter_name():
    assert _adapter().name == "openalex"


def test_engagement_is_cited_by_count():
    item = _adapter()._build_item(_work(cited_by_count=123), "W4400000000")
    assert item.engagement == 123


def test_engagement_zero_when_uncited():
    item = _adapter()._build_item(_work(cited_by_count=0), "W4400000000")
    assert item.engagement == 0


def test_engagement_handles_string_count():
    item = _adapter()._build_item(_work(cited_by_count="55"), "W4400000000")
    assert item.engagement == 55


def test_engagement_handles_null_count():
    item = _adapter()._build_item(_work(cited_by_count=None), "W4400000000")
    assert item.engagement == 0


def test_extract_work_id_from_url():
    assert OpenAlexAdapter._extract_work_id({"id": "https://openalex.org/W7137631773"}) == "W7137631773"


def test_extract_work_id_returns_none_when_missing():
    assert OpenAlexAdapter._extract_work_id({"id": None}) is None
    assert OpenAlexAdapter._extract_work_id({}) is None


def test_extract_work_id_returns_none_when_malformed():
    assert OpenAlexAdapter._extract_work_id({"id": "not-a-url"}) is None


def test_url_prefers_doi():
    item = _adapter()._build_item(
        _work(doi="https://doi.org/10.1234/x"),
        "W4400000000",
    )
    assert item.url == "https://doi.org/10.1234/x"


def test_url_falls_back_to_openalex_page_when_no_doi():
    item = _adapter()._build_item(
        _work(doi=None, id="https://openalex.org/W4400000000"),
        "W4400000000",
    )
    assert item.url == "https://openalex.org/W4400000000"


def test_doi_normalization_wraps_bare_doi():
    """OpenAlex usually returns DOI as URL but accept bare DOIs too."""
    assert OpenAlexAdapter._normalize_doi("10.1234/x") == "https://doi.org/10.1234/x"


def test_doi_normalization_preserves_full_url():
    assert OpenAlexAdapter._normalize_doi("https://doi.org/10.1234/x") == "https://doi.org/10.1234/x"


def test_doi_normalization_none_when_missing():
    assert OpenAlexAdapter._normalize_doi(None) is None
    assert OpenAlexAdapter._normalize_doi("") is None


def test_author_uses_display_name():
    item = _adapter()._build_item(_work(), "W4400000000")
    assert item.author == "Jane Doe et al."


def test_author_single_author():
    work = _work(authorships=[{
        "author_position": "first",
        "author": {"display_name": "Solo Researcher"},
    }])
    item = _adapter()._build_item(work, "W4400000000")
    assert item.author == "Solo Researcher"


def test_author_falls_back_to_raw_author_name():
    """If author.display_name missing, use raw_author_name."""
    work = _work(authorships=[
        {"author_position": "first", "raw_author_name": "Smith, A.", "author": {}},
    ])
    item = _adapter()._build_item(work, "W4400000000")
    assert item.author == "Smith, A."


def test_author_none_when_no_authorships():
    item = _adapter()._build_item(_work(authorships=[]), "W4400000000")
    assert item.author is None


def test_raw_preserves_fwci():
    item = _adapter()._build_item(_work(fwci=2.5), "W4400000000")
    assert item.raw["fwci"] == 2.5


def test_raw_preserves_null_fwci():
    """Too-new papers have fwci=None -- must stay None, not coerce to 0.0."""
    item = _adapter()._build_item(_work(fwci=None), "W4400000000")
    assert item.raw["fwci"] is None


def test_raw_open_access_subset():
    item = _adapter()._build_item(_work(), "W4400000000")
    oa = item.raw["open_access"]
    assert oa["is_oa"] is True
    assert oa["oa_url"] == "https://example.com/paper.pdf"
    assert oa["oa_status"] == "gold"


def test_raw_open_access_handles_missing():
    item = _adapter()._build_item(_work(open_access={}), "W4400000000")
    assert item.raw["open_access"] == {"is_oa": False, "oa_url": None, "oa_status": None}


def test_raw_concepts_strip_url_prefix():
    """Concept IDs come as URLs but the trailing segment is what's useful."""
    work = _work(concepts=[
        {"id": "https://openalex.org/C123", "display_name": "Biology", "level": 0, "score": 0.9}
    ])
    item = _adapter()._build_item(work, "W4400000000")
    assert item.raw["concepts"][0]["id"] == "C123"
    assert item.raw["concepts"][0]["display_name"] == "Biology"


def test_raw_counts_by_year_preserved():
    item = _adapter()._build_item(_work(), "W4400000000")
    assert item.raw["counts_by_year"] == [
        {"year": 2026, "cited_by_count": 30},
        {"year": 2025, "cited_by_count": 12},
    ]


def test_timestamp_parses_publication_date():
    item = _adapter()._build_item(_work(publication_date="2024-07-04"), "W4400000000")
    assert item.timestamp.year == 2024
    assert item.timestamp.month == 7
    assert item.timestamp.day == 4
    assert item.timestamp.tzinfo == timezone.utc


def test_timestamp_falls_back_to_now_when_missing():
    item = _adapter()._build_item(_work(publication_date=None), "W4400000000")
    assert item.timestamp is not None


def test_timestamp_falls_back_when_unparseable():
    item = _adapter()._build_item(_work(publication_date="not-a-date"), "W4400000000")
    assert item.timestamp is not None


def test_source_tier_is_deliberate():
    assert source_tier("openalex") == Tier.DELIBERATE


def test_per_item_bonus_high_fwci():
    assert _per_item_bonus("openalex", {"fwci": 4.0}) == 0.4


def test_per_item_bonus_medium_fwci():
    assert _per_item_bonus("openalex", {"fwci": 1.5}) == 0.2


def test_per_item_bonus_below_average_fwci():
    assert _per_item_bonus("openalex", {"fwci": 0.5}) == 0.0


def test_per_item_bonus_zero_when_fwci_null():
    """Too-new papers shouldn't get a bonus from missing data."""
    assert _per_item_bonus("openalex", {"fwci": None}) == 0.0


def test_per_item_bonus_zero_when_fwci_missing():
    assert _per_item_bonus("openalex", {}) == 0.0


def test_since_date_format():
    """OpenAlex uses the shared `since_date` helper."""
    from digest.adapters._helpers import since_date

    s = since_date(30)
    assert s is not None
    assert len(s) == 10
    assert s[4] == "-"
    assert s[7] == "-"


def test_since_date_none_when_days_zero():
    from digest.adapters._helpers import since_date

    assert since_date(0) is None


def test_adapter_registered():
    from digest.adapters import ADAPTERS, get_adapter

    assert "openalex" in ADAPTERS
    adapter = get_adapter("openalex")
    assert adapter.name == "openalex"
