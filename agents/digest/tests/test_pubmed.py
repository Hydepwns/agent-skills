"""Unit tests for the PubMed adapter.

No mocks. Tests build Items directly from synthetic dicts that mirror the
shape of the NCBI E-utilities esummary response and the iCite response.
Shapes verified against real API responses on 2026-05-13.
"""

from __future__ import annotations

from datetime import timezone

from digest.adapters.pubmed import PubMedAdapter
from digest.credibility import _per_item_bonus, source_tier, Tier


def _adapter() -> PubMedAdapter:
    return PubMedAdapter()


def _summary(**overrides) -> dict:
    """Minimal esummary-shape dict, overridable per test."""
    base = {
        "uid": "40400000",
        "title": "Adaptation mechanisms of Brucella abortus to low magnesium ion stress.",
        "sortpubdate": "2025/05/21 00:00",
        "source": "BMC Vet Res",
        "fulljournalname": "BMC Veterinary Research",
        "pubtype": ["Journal Article"],
        "authors": [
            {"name": "Wang H", "authtype": "Author"},
            {"name": "Lv L", "authtype": "Author"},
            {"name": "Huang Y", "authtype": "Author"},
        ],
        "articleids": [
            {"idtype": "pubmed", "value": "40400000"},
            {"idtype": "doi", "value": "10.1186/s12917-025-04831-8"},
        ],
    }
    base.update(overrides)
    return base


def test_adapter_name():
    assert _adapter().name == "pubmed"


def test_engagement_uses_citation_count():
    item = _adapter()._build_item(
        "40400000",
        _summary(),
        {"pmid": 40400000, "citation_count": 23, "relative_citation_ratio": 1.8, "is_clinical": False},
    )
    assert item.engagement == 23


def test_engagement_zero_when_icite_missing():
    """iCite call may have failed -- engagement should default to 0."""
    item = _adapter()._build_item("40400000", _summary(), {})
    assert item.engagement == 0


def test_engagement_zero_for_uncited_paper():
    item = _adapter()._build_item(
        "40400000",
        _summary(),
        {"pmid": 40400000, "citation_count": 0, "relative_citation_ratio": None, "is_clinical": False},
    )
    assert item.engagement == 0


def test_engagement_handles_string_citation_count():
    item = _adapter()._build_item(
        "40400000",
        _summary(),
        {"citation_count": "42"},
    )
    assert item.engagement == 42


def test_url_uses_pmid():
    item = _adapter()._build_item("40400000", _summary(), {})
    assert item.url == "https://pubmed.ncbi.nlm.nih.gov/40400000/"


def test_author_single():
    item = _adapter()._build_item(
        "40400000",
        _summary(authors=[{"name": "Wang H", "authtype": "Author"}]),
        {},
    )
    assert item.author == "Wang H"


def test_author_multiple_uses_et_al():
    item = _adapter()._build_item("40400000", _summary(), {})
    assert item.author == "Wang H et al."


def test_author_none_when_no_authors():
    item = _adapter()._build_item("40400000", _summary(authors=[]), {})
    assert item.author is None


def test_author_skips_entries_without_name():
    item = _adapter()._build_item(
        "40400000",
        _summary(authors=[{"authtype": "Author"}, {"name": "Real Author"}]),
        {},
    )
    assert item.author == "Real Author"


def test_doi_extracted_from_articleids():
    item = _adapter()._build_item("40400000", _summary(), {})
    assert item.raw["doi"] == "10.1186/s12917-025-04831-8"


def test_doi_none_when_missing():
    item = _adapter()._build_item(
        "40400000",
        _summary(articleids=[{"idtype": "pubmed", "value": "40400000"}]),
        {},
    )
    assert item.raw["doi"] is None


def test_journal_uses_source():
    item = _adapter()._build_item("40400000", _summary(), {})
    assert item.raw["journal"] == "BMC Vet Res"


def test_journal_falls_back_to_fulljournalname():
    item = _adapter()._build_item(
        "40400000",
        _summary(source=None),
        {},
    )
    assert item.raw["journal"] == "BMC Veterinary Research"


def test_raw_preserves_icite_signals():
    item = _adapter()._build_item(
        "40400000",
        _summary(),
        {
            "pmid": 40400000,
            "citation_count": 12,
            "relative_citation_ratio": 2.3,
            "is_clinical": True,
        },
    )
    assert item.raw["pmid"] == "40400000"
    assert item.raw["citation_count"] == 12
    assert item.raw["relative_citation_ratio"] == 2.3
    assert item.raw["is_clinical"] is True
    assert item.raw["pub_types"] == ["Journal Article"]


def test_rcr_null_kept_as_none():
    """iCite returns null RCR for too-new papers; preserve as None, not 0.0."""
    item = _adapter()._build_item(
        "40400000",
        _summary(),
        {"citation_count": 0, "relative_citation_ratio": None},
    )
    assert item.raw["relative_citation_ratio"] is None


def test_pubdate_parses_to_utc():
    item = _adapter()._build_item("40400000", _summary(sortpubdate="2025/05/21 00:00"), {})
    assert item.timestamp.year == 2025
    assert item.timestamp.month == 5
    assert item.timestamp.day == 21
    assert item.timestamp.tzinfo == timezone.utc


def test_pubdate_parses_date_only_format():
    """Some sortpubdate values come back without a time portion."""
    item = _adapter()._build_item("40400000", _summary(sortpubdate="2024/03/15"), {})
    assert item.timestamp.year == 2024
    assert item.timestamp.month == 3
    assert item.timestamp.day == 15


def test_pubdate_fallback_when_missing():
    item = _adapter()._build_item("40400000", _summary(sortpubdate=None), {})
    assert item.timestamp is not None


def test_pubdate_fallback_when_unparseable():
    item = _adapter()._build_item("40400000", _summary(sortpubdate="not-a-date"), {})
    assert item.timestamp is not None


def test_title_falls_back_to_pmid():
    item = _adapter()._build_item("40400000", _summary(title=None), {})
    assert item.title == "40400000"


def test_source_tier_is_deliberate():
    assert source_tier("pubmed") == Tier.DELIBERATE


def test_per_item_bonus_high_rcr():
    raw = {"relative_citation_ratio": 7.5, "is_clinical": False}
    assert _per_item_bonus("pubmed", raw) == 0.4


def test_per_item_bonus_medium_rcr():
    raw = {"relative_citation_ratio": 2.0, "is_clinical": False}
    assert _per_item_bonus("pubmed", raw) == 0.2


def test_per_item_bonus_clinical_only():
    raw = {"relative_citation_ratio": None, "is_clinical": True}
    assert _per_item_bonus("pubmed", raw) == 0.1


def test_per_item_bonus_rcr_plus_clinical():
    raw = {"relative_citation_ratio": 6.0, "is_clinical": True}
    # 0.4 + 0.1 = 0.5
    assert _per_item_bonus("pubmed", raw) == 0.5


def test_per_item_bonus_caps_at_half():
    raw = {"relative_citation_ratio": 10.0, "is_clinical": True}
    # 0.4 + 0.1 = 0.5 (already at cap)
    assert _per_item_bonus("pubmed", raw) == 0.5


def test_per_item_bonus_zero_when_uncited_nonclinical():
    raw = {"relative_citation_ratio": 0.3, "is_clinical": False}
    assert _per_item_bonus("pubmed", raw) == 0.0


def test_per_item_bonus_zero_when_rcr_null():
    raw = {"relative_citation_ratio": None, "is_clinical": False}
    assert _per_item_bonus("pubmed", raw) == 0.0


def test_mindate_helper_uses_slash_format():
    """PubMed uses the shared `since_date` helper with custom slash format."""
    from digest.adapters._helpers import since_date

    mindate = since_date(30, fmt="%Y/%m/%d")
    assert mindate is not None
    assert mindate[4] == "/"
    assert mindate[7] == "/"


def test_adapter_registered():
    from digest.adapters import ADAPTERS, get_adapter

    assert "pubmed" in ADAPTERS
    adapter = get_adapter("pubmed")
    assert adapter.name == "pubmed"
