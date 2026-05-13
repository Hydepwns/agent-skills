"""ClinicalTrials.gov adapter (clinicaltrials.gov/api/v2/studies, no auth).

One `/studies` call per query term. Response shape is deeply nested under
`protocolSection`, so the adapter does careful path traversal rather than
flat dict access.

**HTTP client note**: this adapter uses `urllib.request` from the stdlib
instead of `httpx` (which the rest of digest uses). The CT.gov edge WAF
performs TLS fingerprinting and returns 403 to httpx (and to httpx
mimicking curl's exact headers) regardless of UA. urllib's TLS handshake
is accepted. This is the only adapter that needs to dodge the WAF, so
the special-case is contained here.

Engagement is `enrollment_count + phase_score`, where phase_score weights
the most advanced phase the trial has reached:

    PHASE4 = 40,  PHASE3 = 30,  PHASE2 = 20,  PHASE1 = 10,
    EARLY_PHASE1 = 5,  NA = 0.

A trial may list multiple phases (e.g. ["PHASE1", "PHASE2"]) -- the highest
weight wins for both engagement and the per-item credibility bonus.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone

from digest.adapters._helpers import coerce_int, parse_date_utc
from digest.expansion import ExpandedQuery
from digest.models import Item

API_URL = "https://clinicaltrials.gov/api/v2/studies"

USER_AGENT = "digest-adapter/1.0 (+https://github.com/DROOdotFOO/agent-skills)"

# Phase weights for engagement scoring. Order in this dict also defines the
# ranking when a trial lists multiple phases -- we pick the highest weight.
PHASE_SCORES: dict[str, int] = {
    "PHASE4": 40,
    "PHASE3": 30,
    "PHASE2": 20,
    "PHASE1": 10,
    "EARLY_PHASE1": 5,
    "NA": 0,
}


class ClinicalTrialsAdapter:
    name = "clinicaltrials"

    def fetch(self, query: ExpandedQuery, days: int, limit: int = 50) -> list[Item]:
        """Fetch recent trials matching any query term.

        One `/studies` call per term. Dedupes by nctId. Returns up to `limit`
        items sorted by LastUpdatePostDate desc (server-side).

        Note: the v2 API has no native date-range filter. We sort newest-first
        and return whatever the API gives us; client-side date filtering would
        require a separate timestamp parse per item and adds complexity for
        marginal value on a 50-item digest budget.
        """
        seen: dict[str, Item] = {}

        for term in query.terms:
            for study in self._search(term, limit):
                nct_id = self._extract_nct_id(study)
                if not nct_id or nct_id in seen:
                    continue
                seen[nct_id] = self._build_item(study, nct_id)
                if len(seen) >= limit:
                    return list(seen.values())

        return list(seen.values())[:limit]

    def _search(self, term: str, limit: int) -> list[dict]:
        params = {
            "query.term": term,
            "pageSize": str(min(limit, 100)),
            "sort": "LastUpdatePostDate:desc",
            "format": "json",
        }
        url = f"{API_URL}?{urllib.parse.urlencode(params)}"
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        try:
            with urllib.request.urlopen(req, timeout=30) as response:
                payload = json.load(response)
        except (urllib.error.URLError, json.JSONDecodeError, TimeoutError, OSError):
            return []
        return payload.get("studies") or []

    def _build_item(self, study: dict, nct_id: str) -> Item:
        protocol = study.get("protocolSection") or {}
        ident = protocol.get("identificationModule") or {}
        status = protocol.get("statusModule") or {}
        design = protocol.get("designModule") or {}
        sponsor_mod = protocol.get("sponsorCollaboratorsModule") or {}
        conditions_mod = protocol.get("conditionsModule") or {}
        arms_mod = protocol.get("armsInterventionsModule") or {}

        title = ident.get("briefTitle") or ident.get("officialTitle") or nct_id

        phases = design.get("phases") or []
        top_phase = self._top_phase(phases)
        phase_score = PHASE_SCORES.get(top_phase, 0)

        enrollment_info = design.get("enrollmentInfo") or {}
        enrollment_count = coerce_int(enrollment_info.get("count"))

        engagement = enrollment_count + phase_score

        overall_status = status.get("overallStatus")
        lead_sponsor = (sponsor_mod.get("leadSponsor") or {}).get("name")

        conditions = list(conditions_mod.get("conditions") or [])
        interventions = [
            {"type": i.get("type"), "name": i.get("name")}
            for i in (arms_mod.get("interventions") or [])
            if isinstance(i, dict)
        ]

        start_date = self._struct_date(status.get("startDateStruct"))
        last_update = self._struct_date(status.get("lastUpdatePostDateStruct"))
        timestamp = last_update or start_date or datetime.now(timezone.utc)

        return Item(
            source=self.name,
            title=title,
            url=f"https://clinicaltrials.gov/study/{nct_id}",
            author=lead_sponsor,
            timestamp=timestamp,
            engagement=engagement,
            summary=self._build_summary(overall_status, top_phase, enrollment_count, conditions),
            raw={
                "nctId": nct_id,
                "phase": top_phase,
                "phases": phases,
                "enrollmentCount": enrollment_count,
                "overallStatus": overall_status,
                "conditions": conditions,
                "interventions": interventions,
                "leadSponsor": lead_sponsor,
                "startDate": status.get("startDateStruct", {}).get("date"),
                "lastUpdatePostDate": status.get("lastUpdatePostDateStruct", {}).get("date"),
            },
        )

    @staticmethod
    def _extract_nct_id(study: dict) -> str | None:
        protocol = study.get("protocolSection") or {}
        ident = protocol.get("identificationModule") or {}
        nct = ident.get("nctId")
        if not nct or not isinstance(nct, str):
            return None
        return nct.strip() or None

    @staticmethod
    def _top_phase(phases: list) -> str:
        """Pick the highest-weight phase from a possibly-multi-phase list."""
        if not phases:
            return "NA"
        best = "NA"
        best_score = -1
        for phase in phases:
            if not isinstance(phase, str):
                continue
            score = PHASE_SCORES.get(phase, 0)
            if score > best_score:
                best = phase
                best_score = score
        return best

    @staticmethod
    def _struct_date(value: object) -> datetime | None:
        """Parse a `{date: 'YYYY-MM-DD'|'YYYY-MM'|'YYYY', type: ...}` struct via shared helper."""
        if not isinstance(value, dict):
            return None
        return parse_date_utc(value.get("date"), formats=("%Y-%m-%d", "%Y-%m", "%Y"))

    @staticmethod
    def _build_summary(
        status: str | None,
        phase: str,
        enrollment: int,
        conditions: list,
    ) -> str:
        parts: list[str] = []
        if status:
            parts.append(f"status={status}")
        if phase and phase != "NA":
            parts.append(f"phase={phase}")
        if enrollment > 0:
            parts.append(f"enrollment={enrollment:,}")
        if conditions:
            parts.append(f"conditions={', '.join(conditions[:3])}")
        return " | ".join(parts) if parts else "No metadata available"

