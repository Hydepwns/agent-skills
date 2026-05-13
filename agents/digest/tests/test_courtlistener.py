"""Unit tests for the CourtListener adapter.

No mocks. Synthetic dicts mirror the real /api/rest/v4/search/ response
shape verified against www.courtlistener.com on 2026-05-13.
"""

from __future__ import annotations

from datetime import timezone

from digest.adapters.courtlistener import CourtListenerAdapter, SITE_BASE
from digest.credibility import _per_item_bonus, source_tier, Tier


def _adapter() -> CourtListenerAdapter:
    return CourtListenerAdapter()


def _result(**overrides) -> dict:
    base = {
        "cluster_id": 10858307,
        "caseName": "Gibbs v. County of Humboldt",
        "court": "California Court of Appeal",
        "court_id": "calctapp",
        "dateFiled": "2026-05-13",
        "citeCount": 0,
        "citation": [],
        "judge": "",
        "snippet": None,
        "docketNumber": "A173637",
        "absolute_url": "/opinion/10858307/gibbs-v-county-of-humboldt/",
    }
    base.update(overrides)
    return base


def test_adapter_name():
    assert _adapter().name == "courtlistener"


def test_engagement_is_cite_count():
    item = _adapter()._build_item(_result(citeCount=42), "10858307")
    assert item.engagement == 42


def test_engagement_zero_when_uncited():
    item = _adapter()._build_item(_result(citeCount=0), "10858307")
    assert item.engagement == 0


def test_engagement_handles_string_count():
    item = _adapter()._build_item(_result(citeCount="100"), "10858307")
    assert item.engagement == 100


def test_engagement_handles_null_count():
    item = _adapter()._build_item(_result(citeCount=None), "10858307")
    assert item.engagement == 0


def test_url_built_from_absolute_url():
    item = _adapter()._build_item(_result(), "10858307")
    assert item.url == SITE_BASE + "/opinion/10858307/gibbs-v-county-of-humboldt/"


def test_url_falls_back_to_site_when_missing():
    item = _adapter()._build_item(_result(absolute_url=""), "10858307")
    assert item.url == SITE_BASE


def test_url_handles_already_absolute():
    item = _adapter()._build_item(
        _result(absolute_url="https://other.example.com/opinion/x/"),
        "10858307",
    )
    assert item.url == "https://other.example.com/opinion/x/"


def test_url_prepends_slash_when_missing():
    """Defensive: if absolute_url comes back without leading slash, still build a valid URL."""
    item = _adapter()._build_item(_result(absolute_url="opinion/x/"), "10858307")
    assert item.url == SITE_BASE + "/opinion/x/"


def test_title_is_case_name():
    item = _adapter()._build_item(_result(caseName="Roe v. Wade"), "10858307")
    assert item.title == "Roe v. Wade"


def test_title_falls_back_to_cluster_id():
    item = _adapter()._build_item(_result(caseName=None), "10858307")
    assert item.title == "10858307"


def test_judge_single():
    item = _adapter()._build_item(_result(judge="Judge Amit P. Mehta"), "10858307")
    assert item.author == "Judge Amit P. Mehta"


def test_judge_panel_uses_et_al():
    """Multi-judge panels are semicolon-separated."""
    item = _adapter()._build_item(
        _result(judge="Julia Smith Gibbons; Amul R. Thapar; Joan L. Larsen"),
        "10858307",
    )
    assert item.author == "Julia Smith Gibbons et al."


def test_judge_empty_string_is_none():
    item = _adapter()._build_item(_result(judge=""), "10858307")
    assert item.author is None


def test_judge_whitespace_only_is_none():
    item = _adapter()._build_item(_result(judge="   "), "10858307")
    assert item.author is None


def test_judge_none_is_none():
    item = _adapter()._build_item(_result(judge=None), "10858307")
    assert item.author is None


def test_summary_uses_snippet_when_present():
    item = _adapter()._build_item(_result(snippet="...due process and qualified immunity..."), "10858307")
    assert item.summary == "...due process and qualified immunity..."


def test_summary_none_when_snippet_empty():
    item = _adapter()._build_item(_result(snippet=""), "10858307")
    assert item.summary is None


def test_summary_none_when_snippet_missing():
    item = _adapter()._build_item(_result(snippet=None), "10858307")
    assert item.summary is None


def test_raw_preserves_court_and_court_id():
    item = _adapter()._build_item(_result(court="U.S. Supreme Court", court_id="scotus"), "10858307")
    assert item.raw["court"] == "U.S. Supreme Court"
    assert item.raw["court_id"] == "scotus"


def test_raw_court_falls_back_to_court_id():
    """When `court` is None but `court_id` is set, preserve the short code."""
    item = _adapter()._build_item(_result(court=None, court_id="ca6"), "10858307")
    assert item.raw["court"] == "ca6"


def test_raw_court_none_when_both_missing():
    item = _adapter()._build_item(_result(court=None, court_id=""), "10858307")
    assert item.raw["court"] is None


def test_raw_preserves_citation_list():
    item = _adapter()._build_item(_result(citation=["410 U.S. 113"]), "10858307")
    assert item.raw["citation"] == ["410 U.S. 113"]


def test_raw_preserves_docket_number():
    item = _adapter()._build_item(_result(docketNumber="22-1234"), "10858307")
    assert item.raw["docketNumber"] == "22-1234"


def test_timestamp_parses_date_filed():
    item = _adapter()._build_item(_result(dateFiled="1973-01-22"), "10858307")
    assert item.timestamp.year == 1973
    assert item.timestamp.month == 1
    assert item.timestamp.day == 22
    assert item.timestamp.tzinfo == timezone.utc


def test_timestamp_falls_back_when_missing():
    item = _adapter()._build_item(_result(dateFiled=None), "10858307")
    assert item.timestamp is not None


def test_timestamp_falls_back_when_unparseable():
    item = _adapter()._build_item(_result(dateFiled="not-a-date"), "10858307")
    assert item.timestamp is not None


def test_source_tier_is_deliberate():
    assert source_tier("courtlistener") == Tier.DELIBERATE


def test_per_item_bonus_high_cite_count():
    raw = {"citeCount": 200, "court_id": "ca6"}
    assert _per_item_bonus("courtlistener", raw) == 0.4


def test_per_item_bonus_medium_cite_count():
    raw = {"citeCount": 30, "court_id": "ca6"}
    assert _per_item_bonus("courtlistener", raw) == 0.2


def test_per_item_bonus_scotus_only():
    """A new SCOTUS opinion with no citations still gets the court bonus."""
    raw = {"citeCount": 0, "court_id": "scotus"}
    assert _per_item_bonus("courtlistener", raw) == 0.3


def test_per_item_bonus_scotus_plus_cites():
    """SCOTUS + 30 cites = 0.3 + 0.2 = 0.5 (at cap)."""
    raw = {"citeCount": 30, "court_id": "scotus"}
    assert _per_item_bonus("courtlistener", raw) == 0.5


def test_per_item_bonus_scotus_plus_many_cites_caps():
    """SCOTUS + 200 cites = 0.3 + 0.4 = 0.7, capped at 0.5."""
    raw = {"citeCount": 200, "court_id": "scotus"}
    assert _per_item_bonus("courtlistener", raw) == 0.5


def test_per_item_bonus_zero_for_recent_lower_court_opinion():
    """A new opinion from a lower court with no citations gets nothing."""
    raw = {"citeCount": 0, "court_id": "calctapp"}
    assert _per_item_bonus("courtlistener", raw) == 0.0


def test_per_item_bonus_zero_for_missing_data():
    assert _per_item_bonus("courtlistener", {}) == 0.0


def test_since_date_format():
    """CourtListener uses the shared `since_date` helper."""
    from digest.adapters._helpers import since_date

    s = since_date(30)
    assert s is not None
    assert len(s) == 10


def test_since_date_none_when_days_zero():
    from digest.adapters._helpers import since_date

    assert since_date(0) is None


def test_adapter_registered():
    from digest.adapters import ADAPTERS, get_adapter

    assert "courtlistener" in ADAPTERS
    adapter = get_adapter("courtlistener")
    assert adapter.name == "courtlistener"
