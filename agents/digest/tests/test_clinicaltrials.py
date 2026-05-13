"""Unit tests for the ClinicalTrials.gov adapter.

No mocks. Synthetic dicts mirror the real /api/v2/studies response shape
verified against clinicaltrials.gov on 2026-05-13.
"""

from __future__ import annotations

from datetime import timezone

from digest.adapters.clinicaltrials import PHASE_SCORES, ClinicalTrialsAdapter
from digest.credibility import _per_item_bonus, source_tier, Tier


def _adapter() -> ClinicalTrialsAdapter:
    return ClinicalTrialsAdapter()


def _study(
    *,
    nct_id: str = "NCT06038617",
    brief_title: str = "Safety of mRNA COVID-19 Vaccine With Other Childhood Vaccines",
    official_title: str | None = "A Prospective, Randomized, Open-label Trial",
    phases: list[str] | None = None,
    enrollment_count: int | None = 347,
    overall_status: str = "COMPLETED",
    lead_sponsor: str | None = "Duke University",
    conditions: list[str] | None = None,
    interventions: list[dict] | None = None,
    start_date: str | None = "2023-10-30",
    last_update: str | None = "2026-05-13",
) -> dict:
    """Build a study dict matching the deeply-nested v2 API shape."""
    if phases is None:
        phases = ["PHASE4"]
    if conditions is None:
        conditions = ["Fever After Vaccination", "Fever", "Seizures Fever"]
    if interventions is None:
        interventions = [
            {"type": "BIOLOGICAL", "name": "mRNA COVID-19 Vaccine"},
            {"type": "BIOLOGICAL", "name": "Routine Childhood Vaccinations"},
        ]

    protocol: dict = {
        "identificationModule": {
            "nctId": nct_id,
            "briefTitle": brief_title,
            "officialTitle": official_title,
        },
        "statusModule": {
            "overallStatus": overall_status,
        },
        "designModule": {
            "phases": phases,
            "enrollmentInfo": {"count": enrollment_count} if enrollment_count is not None else {},
        },
        "sponsorCollaboratorsModule": {
            "leadSponsor": {"name": lead_sponsor, "class": "OTHER"} if lead_sponsor else {},
        },
        "conditionsModule": {"conditions": conditions},
        "armsInterventionsModule": {"interventions": interventions},
    }
    if start_date:
        protocol["statusModule"]["startDateStruct"] = {"date": start_date, "type": "ACTUAL"}
    if last_update:
        protocol["statusModule"]["lastUpdatePostDateStruct"] = {"date": last_update, "type": "ACTUAL"}

    return {"protocolSection": protocol}


def test_adapter_name():
    assert _adapter().name == "clinicaltrials"


def test_engagement_combines_enrollment_and_phase_score():
    study = _study(phases=["PHASE3"], enrollment_count=500)
    item = _adapter()._build_item(study, "NCT06038617")
    # 500 + 30 (PHASE3 score)
    assert item.engagement == 530


def test_engagement_uses_highest_phase_when_multiple():
    study = _study(phases=["PHASE1", "PHASE2"], enrollment_count=100)
    item = _adapter()._build_item(study, "NCT06038617")
    # 100 + 20 (PHASE2 wins over PHASE1)
    assert item.engagement == 120


def test_engagement_zero_phase_for_na():
    study = _study(phases=["NA"], enrollment_count=50)
    item = _adapter()._build_item(study, "NCT06038617")
    assert item.engagement == 50


def test_engagement_zero_phase_for_missing_phases():
    study = _study(phases=[], enrollment_count=10)
    item = _adapter()._build_item(study, "NCT06038617")
    assert item.engagement == 10


def test_engagement_handles_missing_enrollment():
    study = _study(phases=["PHASE3"], enrollment_count=None)
    item = _adapter()._build_item(study, "NCT06038617")
    # 0 + 30
    assert item.engagement == 30


def test_top_phase_picks_highest_weight():
    assert ClinicalTrialsAdapter._top_phase(["PHASE1", "PHASE3", "PHASE2"]) == "PHASE3"
    assert ClinicalTrialsAdapter._top_phase(["PHASE4"]) == "PHASE4"
    assert ClinicalTrialsAdapter._top_phase(["EARLY_PHASE1", "PHASE1"]) == "PHASE1"


def test_top_phase_handles_unknown_phase():
    """Unknown phase strings get a default score of 0 but the highest known one wins."""
    assert ClinicalTrialsAdapter._top_phase(["PHASE3", "WEIRD_PHASE"]) == "PHASE3"


def test_top_phase_returns_na_for_empty():
    assert ClinicalTrialsAdapter._top_phase([]) == "NA"


def test_phase_scores_have_expected_weights():
    """Guard against accidental edits to the weight table."""
    assert PHASE_SCORES["PHASE4"] == 40
    assert PHASE_SCORES["PHASE3"] == 30
    assert PHASE_SCORES["PHASE2"] == 20
    assert PHASE_SCORES["PHASE1"] == 10
    assert PHASE_SCORES["EARLY_PHASE1"] == 5
    assert PHASE_SCORES["NA"] == 0


def test_url_uses_nct_id():
    item = _adapter()._build_item(_study(), "NCT06038617")
    assert item.url == "https://clinicaltrials.gov/study/NCT06038617"


def test_title_prefers_brief_title():
    item = _adapter()._build_item(_study(brief_title="Brief", official_title="Official"), "NCT06038617")
    assert item.title == "Brief"


def test_title_falls_back_to_official_title():
    item = _adapter()._build_item(_study(brief_title=None, official_title="Official"), "NCT06038617")
    assert item.title == "Official"


def test_title_falls_back_to_nct_id():
    item = _adapter()._build_item(_study(brief_title=None, official_title=None), "NCT06038617")
    assert item.title == "NCT06038617"


def test_author_is_lead_sponsor():
    item = _adapter()._build_item(_study(lead_sponsor="Pfizer"), "NCT06038617")
    assert item.author == "Pfizer"


def test_author_none_when_sponsor_missing():
    item = _adapter()._build_item(_study(lead_sponsor=None), "NCT06038617")
    assert item.author is None


def test_summary_includes_status_phase_enrollment_conditions():
    item = _adapter()._build_item(
        _study(
            overall_status="RECRUITING",
            phases=["PHASE3"],
            enrollment_count=5000,
            conditions=["Diabetes", "Hypertension"],
        ),
        "NCT06038617",
    )
    assert "status=RECRUITING" in item.summary
    assert "phase=PHASE3" in item.summary
    assert "enrollment=5,000" in item.summary
    assert "Diabetes" in item.summary


def test_summary_omits_phase_when_na():
    item = _adapter()._build_item(_study(phases=["NA"]), "NCT06038617")
    assert "phase=" not in item.summary


def test_raw_preserves_phases_list_and_top_phase():
    study = _study(phases=["PHASE2", "PHASE3"])
    item = _adapter()._build_item(study, "NCT06038617")
    assert item.raw["phases"] == ["PHASE2", "PHASE3"]
    assert item.raw["phase"] == "PHASE3"


def test_raw_preserves_interventions():
    item = _adapter()._build_item(_study(), "NCT06038617")
    assert item.raw["interventions"][0]["name"] == "mRNA COVID-19 Vaccine"
    assert item.raw["interventions"][0]["type"] == "BIOLOGICAL"


def test_raw_preserves_conditions():
    item = _adapter()._build_item(_study(conditions=["Cancer", "Lymphoma"]), "NCT06038617")
    assert item.raw["conditions"] == ["Cancer", "Lymphoma"]


def test_raw_preserves_dates():
    item = _adapter()._build_item(_study(start_date="2024-01-15", last_update="2026-05-13"), "NCT06038617")
    assert item.raw["startDate"] == "2024-01-15"
    assert item.raw["lastUpdatePostDate"] == "2026-05-13"


def test_timestamp_prefers_last_update():
    item = _adapter()._build_item(
        _study(start_date="2023-01-01", last_update="2026-05-13"),
        "NCT06038617",
    )
    assert item.timestamp.year == 2026
    assert item.timestamp.month == 5
    assert item.timestamp.day == 13
    assert item.timestamp.tzinfo == timezone.utc


def test_timestamp_falls_back_to_start_date():
    item = _adapter()._build_item(
        _study(start_date="2024-03-01", last_update=None),
        "NCT06038617",
    )
    assert item.timestamp.year == 2024
    assert item.timestamp.month == 3


def test_timestamp_handles_year_month_format():
    """Some trials use 'YYYY-MM' for less precise date estimates."""
    item = _adapter()._build_item(
        _study(start_date="2024-06", last_update=None),
        "NCT06038617",
    )
    assert item.timestamp.year == 2024
    assert item.timestamp.month == 6
    assert item.timestamp.day == 1


def test_timestamp_falls_back_to_now_when_missing():
    item = _adapter()._build_item(_study(start_date=None, last_update=None), "NCT06038617")
    assert item.timestamp is not None


def test_extract_nct_id_from_study():
    study = _study(nct_id="NCT12345678")
    assert ClinicalTrialsAdapter._extract_nct_id(study) == "NCT12345678"


def test_extract_nct_id_none_when_missing():
    assert ClinicalTrialsAdapter._extract_nct_id({"protocolSection": {}}) is None
    assert ClinicalTrialsAdapter._extract_nct_id({}) is None


def test_source_tier_is_verified():
    assert source_tier("clinicaltrials") == Tier.VERIFIED


def test_per_item_bonus_phase3():
    raw = {"phase": "PHASE3", "enrollmentCount": 50}
    assert _per_item_bonus("clinicaltrials", raw) == 0.4


def test_per_item_bonus_phase4():
    raw = {"phase": "PHASE4", "enrollmentCount": 50}
    assert _per_item_bonus("clinicaltrials", raw) == 0.4


def test_per_item_bonus_phase2():
    raw = {"phase": "PHASE2", "enrollmentCount": 50}
    assert _per_item_bonus("clinicaltrials", raw) == 0.2


def test_per_item_bonus_phase1_only():
    raw = {"phase": "PHASE1", "enrollmentCount": 50}
    assert _per_item_bonus("clinicaltrials", raw) == 0.0


def test_per_item_bonus_large_enrollment_only():
    raw = {"phase": "NA", "enrollmentCount": 5000}
    assert _per_item_bonus("clinicaltrials", raw) == 0.3


def test_per_item_bonus_phase3_plus_large_enrollment_caps():
    """PHASE3 (0.4) + 5k enrollment (0.3) = 0.7, capped at 0.5."""
    raw = {"phase": "PHASE3", "enrollmentCount": 5000}
    assert _per_item_bonus("clinicaltrials", raw) == 0.5


def test_per_item_bonus_phase2_plus_large_enrollment():
    """PHASE2 (0.2) + 5k enrollment (0.3) = 0.5 (at cap)."""
    raw = {"phase": "PHASE2", "enrollmentCount": 5000}
    assert _per_item_bonus("clinicaltrials", raw) == 0.5


def test_per_item_bonus_zero_for_early_phase_small():
    raw = {"phase": "EARLY_PHASE1", "enrollmentCount": 20}
    assert _per_item_bonus("clinicaltrials", raw) == 0.0


def test_per_item_bonus_zero_for_missing_data():
    assert _per_item_bonus("clinicaltrials", {}) == 0.0


def test_adapter_registered():
    from digest.adapters import ADAPTERS, get_adapter

    assert "clinicaltrials" in ADAPTERS
    adapter = get_adapter("clinicaltrials")
    assert adapter.name == "clinicaltrials"
