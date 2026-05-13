"""Source credibility scoring.

Three-tier model: verified stakes > deliberate engagement > passive volume.
Each item gets a credibility multiplier based on what kind of signal backs it.
Items can also carry per-item credibility signals extracted from raw data.
"""

from __future__ import annotations

from enum import Enum

from digest.models import Item


class Tier(str, Enum):
    """Credibility tier. Higher tiers carry stronger signal."""

    VERIFIED = "verified"  # real money or governance votes
    DELIBERATE = "deliberate"  # active engagement requiring intent
    PASSIVE = "passive"  # views, downloads, market cap -- noisy


# Map source -> tier
SOURCE_TIERS: dict[str, Tier] = {
    "polymarket": Tier.VERIFIED,  # real money at stake
    "snapshot": Tier.VERIFIED,  # governance votes (token-weighted)
    "blockscout": Tier.VERIFIED,  # on-chain transactions (ETH at stake)
    "hn": Tier.DELIBERATE,  # upvotes require account, sparse
    "ethresearch": Tier.DELIBERATE,  # research forum, expert audience
    "github": Tier.DELIBERATE,  # stars from developers
    "reddit": Tier.DELIBERATE,  # votes, comments
    "youtube": Tier.PASSIVE,  # views are passive consumption
    "packages": Tier.PASSIVE,  # downloads are CI/automation heavy
    "coingecko": Tier.PASSIVE,  # market cap is momentum, not conviction
    "shodan": Tier.DELIBERATE,  # intentional exposure data, security research
    "federalregister": Tier.VERIFIED,  # official rulemaking record; comments are deliberate
    "pubmed": Tier.DELIBERATE,  # peer-reviewed citations from other researchers
    "semanticscholar": Tier.DELIBERATE,  # citations + influential-citation signal
    "arxiv": Tier.DELIBERATE,  # preprints, intentional submission; no engagement signal
    "openalex": Tier.DELIBERATE,  # citations across 470M+ works
    "courtlistener": Tier.DELIBERATE,  # opinion citations from other courts
    "clinicaltrials": Tier.VERIFIED,  # registered trials with regulatory oversight
}

# Base multiplier per tier
TIER_MULTIPLIERS: dict[Tier, float] = {
    Tier.VERIFIED: 1.8,
    Tier.DELIBERATE: 1.0,
    Tier.PASSIVE: 0.5,
}


def source_tier(source: str) -> Tier:
    """Get the credibility tier for a platform source."""
    return SOURCE_TIERS.get(source, Tier.PASSIVE)


def credibility_multiplier(
    item: Item,
    historical_accuracy: float = 1.0,
) -> float:
    """Compute a credibility multiplier for an item.

    Three factors:
    1. Source tier (verified/deliberate/passive)
    2. Per-item signals from raw data
    3. Historical accuracy from source_tracker (how well this source's
       items held up in past digests -- 0.5 to 1.5, default 1.0)

    - Polymarket: higher liquidity = more credible odds
    - Snapshot: more votes = stronger governance signal
    - GitHub: repos with issues+forks = real usage, not just stars
    - Blockscout: higher tx value = stronger signal
    - CoinGecko: top-ranked coins more credible than micro-caps
    """
    tier = source_tier(item.source)
    base = TIER_MULTIPLIERS[tier]

    raw = item.raw
    bonus = _per_item_bonus(item.source, raw) if raw else 0.0

    return (base + bonus) * historical_accuracy


def _per_item_bonus(source: str, raw: dict) -> float:
    """Extract per-item credibility bonus from raw data. Returns 0.0-0.5."""
    if source == "polymarket":
        liquidity = raw.get("liquidity", 0)
        if liquidity > 100_000:
            return 0.5
        if liquidity > 10_000:
            return 0.2
        return 0.0

    if source == "snapshot":
        votes = raw.get("votes", 0)
        if votes > 1000:
            return 0.4
        if votes > 100:
            return 0.2
        return 0.0

    if source == "github":
        forks = raw.get("forks", 0)
        issues = raw.get("open_issues", 0)
        if forks > 100 or issues > 50:
            return 0.3
        if forks > 10:
            return 0.1
        return 0.0

    if source == "blockscout":
        value = raw.get("value_eth", 0) or raw.get("amount", 0)
        if value > 100:
            return 0.5
        if value > 1:
            return 0.2
        return 0.0

    if source == "coingecko":
        rank = raw.get("market_cap_rank", 9999)
        if rank <= 50:
            return 0.3
        if rank <= 200:
            return 0.1
        return 0.0

    if source == "hn":
        points = raw.get("points", 0)
        comments = raw.get("num_comments", 0)
        if points > 200 and comments > 50:
            return 0.3
        if points > 50:
            return 0.1
        return 0.0

    if source == "ethresearch":
        likes = raw.get("like_count", 0)
        posts = raw.get("posts_count", 0)
        if likes > 20 or posts > 10:
            return 0.3
        return 0.0

    if source == "shodan":
        vulns = raw.get("vulns", [])
        tags = raw.get("tags", [])
        if len(vulns) >= 5:
            return 0.4
        if len(vulns) >= 1 or len(tags) >= 3:
            return 0.2
        return 0.0

    if source == "federalregister":
        page_views = raw.get("page_views", 0)
        significant = raw.get("significant", False)
        bonus = 0.0
        if significant:
            bonus += 0.3
        if page_views > 10000:
            bonus += 0.4
        elif page_views > 1000:
            bonus += 0.2
        return min(bonus, 0.5)

    if source == "pubmed":
        rcr = raw.get("relative_citation_ratio")
        is_clinical = raw.get("is_clinical", False)
        bonus = 0.0
        if isinstance(rcr, (int, float)):
            if rcr > 5.0:
                bonus += 0.4
            elif rcr > 1.0:
                bonus += 0.2
        if is_clinical:
            bonus += 0.1
        return min(bonus, 0.5)

    if source == "semanticscholar":
        influential = raw.get("influentialCitationCount", 0)
        if influential > 50:
            return 0.4
        if influential > 10:
            return 0.2
        return 0.0

    if source == "openalex":
        fwci = raw.get("fwci")
        if isinstance(fwci, (int, float)):
            if fwci > 3.0:
                return 0.4
            if fwci > 1.0:
                return 0.2
        return 0.0

    if source == "courtlistener":
        cite_count = raw.get("citeCount", 0)
        court_id = raw.get("court_id", "")
        bonus = 0.0
        if cite_count > 100:
            bonus += 0.4
        elif cite_count > 20:
            bonus += 0.2
        if court_id == "scotus":
            bonus += 0.3
        return min(bonus, 0.5)

    if source == "clinicaltrials":
        phase = raw.get("phase", "NA")
        enrollment = raw.get("enrollmentCount", 0)
        bonus = 0.0
        if phase in ("PHASE3", "PHASE4"):
            bonus += 0.4
        elif phase == "PHASE2":
            bonus += 0.2
        if enrollment > 1000:
            bonus += 0.3
        return min(bonus, 0.5)

    return 0.0
