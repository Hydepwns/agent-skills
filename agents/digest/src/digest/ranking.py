"""Engagement-weighted ranking across platforms with credibility scoring.

Three-layer scoring:
1. Log-weighted engagement (normalized per platform)
2. Recency decay (linear over 30 days)
3. Credibility multiplier (verified stakes > deliberate > passive)
"""

from __future__ import annotations

import math
from datetime import datetime, timezone

from digest.credibility import credibility_multiplier
from digest.models import Item

# Platform-specific weights to normalize engagement scales.
# HN upvotes are sparser than GitHub stars, so weight them higher.
PLATFORM_WEIGHTS: dict[str, float] = {
    "hn": 2.0,
    "github": 1.0,
    "reddit": 1.5,
    "youtube": 0.5,
    "shodan": 1.2,  # security exposure data, real services
    "ethresearch": 2.5,  # High-signal research forum, sparse engagement
    "snapshot": 1.5,  # Governance votes are deliberate signals
    "polymarket": 0.8,  # Volume is noisy, but odds are credibility signals
    "packages": 0.3,  # Downloads are massive numbers, scale down heavily
    "coingecko": 0.4,  # Market data, not discussion
    "blockscout": 1.2,  # On-chain activity, real value transfers
    "federalregister": 1.2,  # Official rulemaking; comment counts are concentrated
    "pubmed": 2.5,  # Peer-reviewed citations are sparse but high-signal
    "semanticscholar": 2.5,  # Same: citations across 215M papers, sparse signal
    "arxiv": 2.0,  # No engagement; recency-only. Composite with S2 for citations.
    "openalex": 2.0,  # Citations across humanities + sciences; broad but noisier.
    "courtlistener": 2.0,  # Case law citations are sparse but high-quality
    "clinicaltrials": 1.5,  # Enrollment + phase carry actual clinical commitment
}


# Module-level cache for historical accuracy scores per topic.
# Set by rank() when source_tracker data is available, read by score().
_historical_accuracy: dict[str, float] = {}


def score(item: Item, now: datetime | None = None) -> float:
    """Score an item by engagement * recency * credibility.

    Engagement is log-scaled so a 1000-point story doesn't drown a 50-point one.
    Recency decays linearly over 30 days.
    Credibility adjusts based on signal quality (verified > deliberate > passive),
    modified by historical source accuracy when available.
    """
    now = now or datetime.now(timezone.utc)
    weight = PLATFORM_WEIGHTS.get(item.source, 1.0)
    engagement_score = math.log1p(max(item.engagement, 0)) * weight

    age_days = max((now - item.timestamp).total_seconds() / 86400, 0)
    recency = max(1.0 - age_days / 30, 0.1)

    accuracy = _historical_accuracy.get(item.source, 1.0)
    cred = credibility_multiplier(item, historical_accuracy=accuracy)

    return engagement_score * (0.7 + 0.3 * recency) * cred


def rank(
    items: list[Item],
    limit: int | None = None,
    topic: str | None = None,
) -> list[Item]:
    """Return items sorted by score descending, optionally truncated.

    When topic is provided, loads historical source accuracy from the
    source_tracker to adjust credibility scores.
    """
    global _historical_accuracy

    if topic:
        try:
            from digest.source_tracker import SourceTracker

            tracker = SourceTracker()
            scores = tracker.get_all_scores(topic)
            _historical_accuracy = {s: d["accuracy"] for s, d in scores.items()}
            tracker.close()
        except Exception:
            _historical_accuracy = {}
    else:
        _historical_accuracy = {}

    ranked = sorted(items, key=score, reverse=True)
    _historical_accuracy = {}  # clean up after ranking
    return ranked[:limit] if limit else ranked
