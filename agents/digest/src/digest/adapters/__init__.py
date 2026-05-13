"""Platform adapters for fetching items."""

from digest.adapters.arxiv import ArxivAdapter
from digest.adapters.base import Adapter
from digest.adapters.blockscout import BlockscoutAdapter
from digest.adapters.clinicaltrials import ClinicalTrialsAdapter
from digest.adapters.coingecko import CoinGeckoAdapter
from digest.adapters.courtlistener import CourtListenerAdapter
from digest.adapters.ethresearch import EthResearchAdapter
from digest.adapters.federalregister import FederalRegisterAdapter
from digest.adapters.github import GitHubAdapter
from digest.adapters.hackernews import HackerNewsAdapter
from digest.adapters.openalex import OpenAlexAdapter
from digest.adapters.packages import PackagesAdapter
from digest.adapters.polymarket import PolymarketAdapter
from digest.adapters.pubmed import PubMedAdapter
from digest.adapters.reddit import RedditAdapter
from digest.adapters.semanticscholar import SemanticScholarAdapter
from digest.adapters.shodan import ShodanAdapter
from digest.adapters.snapshot import SnapshotAdapter
from digest.adapters.youtube import YouTubeAdapter

ADAPTERS: dict[str, type[Adapter]] = {
    "hn": HackerNewsAdapter,
    "github": GitHubAdapter,
    "reddit": RedditAdapter,
    "youtube": YouTubeAdapter,
    "snapshot": SnapshotAdapter,
    "ethresearch": EthResearchAdapter,
    "polymarket": PolymarketAdapter,
    "packages": PackagesAdapter,
    "coingecko": CoinGeckoAdapter,
    "blockscout": BlockscoutAdapter,
    "shodan": ShodanAdapter,
    "federalregister": FederalRegisterAdapter,
    "pubmed": PubMedAdapter,
    "semanticscholar": SemanticScholarAdapter,
    "arxiv": ArxivAdapter,
    "openalex": OpenAlexAdapter,
    "courtlistener": CourtListenerAdapter,
    "clinicaltrials": ClinicalTrialsAdapter,
}


def get_adapter(name: str) -> Adapter:
    if name not in ADAPTERS:
        raise ValueError(f"Unknown adapter: {name}. Available: {list(ADAPTERS)}")
    return ADAPTERS[name]()
