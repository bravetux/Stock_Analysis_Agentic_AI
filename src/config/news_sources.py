# =============================================================================
# Author : B.Vignesh Kumar aka Bravetux <ic19939@gmail.com>
# Date   : 10 April 2026
# =============================================================================

"""
Loads news sources from news_sources.yaml and provides them to news tools.
"""

import logging
import pathlib
from dataclasses import dataclass
from functools import lru_cache

import yaml

logger = logging.getLogger(__name__)

_SOURCES_PATH = pathlib.Path(__file__).parent / "news_sources.yaml"


@dataclass(frozen=True)
class NewsSource:
    name: str
    domain: str
    category: str  # general, analysis, data, regulatory, community
    enabled: bool


@lru_cache(maxsize=1)
def _load_all() -> dict[str, list[NewsSource]]:
    """Load and cache all news sources from YAML, keyed by region."""
    with open(_SOURCES_PATH, encoding="utf-8") as f:
        raw = yaml.safe_load(f)

    result: dict[str, list[NewsSource]] = {}
    for region, entries in raw.items():
        sources = []
        for entry in entries:
            sources.append(NewsSource(
                name=entry["name"],
                domain=entry["domain"],
                category=entry.get("category", "general"),
                enabled=entry.get("enabled", True),
            ))
        result[region] = sources
    return result


def get_sources(region: str, *, include_global: bool = True) -> list[NewsSource]:
    """
    Get enabled news sources for a region.

    Args:
        region: "india" or "us"
        include_global: Whether to append globally-applicable sources.

    Returns:
        List of enabled NewsSource objects.
    """
    all_sources = _load_all()
    sources = [s for s in all_sources.get(region, []) if s.enabled]
    if include_global:
        sources.extend(s for s in all_sources.get("global", []) if s.enabled)
    return sources


def get_location_search_sources(region: str) -> list[dict[str, str]]:
    """
    Get sources formatted for location-based Google News site: searches.

    Returns list of {"name": ..., "query_template": "{ticker} site:domain"}.
    """
    return [
        {"name": s.name, "query_template": "{ticker} site:" + s.domain}
        for s in get_sources(region, include_global=False)
    ]


def get_location_query_templates(region: str, limit: int = 5) -> list[str]:
    """
    Get search query templates for the 100-query batch system.
    Returns templates like "{company} moneycontrol analysis".

    Args:
        region: "india" or "us"
        limit: Max number of templates to return.
    """
    sources = get_sources(region, include_global=False)
    # Prefer general and analysis sources for query templates
    priority = {"general": 0, "analysis": 1, "data": 2, "community": 3, "regulatory": 4}
    sources.sort(key=lambda s: priority.get(s.category, 99))
    templates = []
    for s in sources[:limit]:
        # Use the source name as a keyword in the query
        keyword = s.name.lower().replace("'", "")
        templates.append("{company} " + keyword + " analysis")
    return templates
