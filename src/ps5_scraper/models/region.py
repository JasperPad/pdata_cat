"""Region model for PS Store multi-region support (v2.0).

Defines:
- Region: Pydantic model for a PS Store region configuration
- REGIONS: Predefined dictionary of all known regions (keys UPPERCASE)
- get_region(): Case-insensitive lookup helper
- get_enabled_regions(): Filter helper for active regions
"""

from __future__ import annotations

from pydantic import BaseModel, Field


class Region(BaseModel):
    """Configuration for a PlayStation Store region.

    Each region has a unique locale and currency combination that determines
    which store catalog and pricing the API returns.

    Attributes:
        code: Short identifier — **UPPERCASE** (e.g., "HK", "US", "JP").
        locale: BCP 47 locale tag for the API header (e.g., "zh-hant-hk").
        currency: ISO 4217 currency code for GraphQL variable (e.g., "HKD", "USD").
        name: Human-readable display name in Chinese (e.g., "港服", "美服").
        language: Optional BCP 47 language subtag.
        enabled: Whether this region is available for collection.
        priority: Lower value = higher priority (used for ordering).
    """

    code: str
    locale: str
    currency: str
    name: str
    language: str = ""
    enabled: bool = True
    priority: int = 0


# ─── Predefined Regions ──────────────────────────────────────────
# Based on MULTI_REGION_RESEARCH_REPORT.md findings.
# All keys and .code values are **UPPERCASE** for consistency.
# TODO: Add AU, CA, MX, SG, ID, TH, EU regions in future iteration.

REGIONS: dict[str, Region] = {
    "US": Region(
        code="US",
        locale="en-us",
        currency="USD",
        name="美服",
        priority=1,
    ),
    "JP": Region(
        code="JP",
        locale="ja-jp",
        currency="JPY",
        name="日服",
        priority=2,
    ),
    "UK": Region(
        code="UK",
        locale="en-gb",
        currency="GBP",
        name="英服",
        priority=3,
    ),
    "DE": Region(
        code="DE",
        locale="de-de",
        currency="EUR",
        name="德服",
        priority=4,
    ),
    "KR": Region(
        code="KR",
        locale="ko-kr",
        currency="KRW",
        name="韩服",
        priority=5,
    ),
    "TW": Region(
        code="TW",
        locale="zh-hant-tw",
        currency="TWD",
        name="台服",
        priority=6,
    ),
    "BR": Region(
        code="BR",
        locale="pt-br",
        currency="BRL",
        name="巴西服",
        priority=7,
    ),
    "HK": Region(
        code="HK",
        locale="zh-hant-hk",
        currency="HKD",
        name="港服",
        priority=10,
    ),
    # Disabled regions (low game count or issues)
    "CN": Region(
        code="CN",
        locale="zh-cn",
        currency="CNY",
        name="国服",
        enabled=False,
        priority=99,
    ),
}


# ─── Helper Functions ───────────────────────────────────────────


def get_region(code: str) -> Region | None:
    """Look up a region by its short code (case-insensitive).

    Args:
        code: Region code (e.g., "hk", "HK", "Us", "JP"). Case-insensitive.

    Returns:
        Region instance if found, None otherwise.
    """
    return REGIONS.get(code.upper())


def get_enabled_regions() -> list[Region]:
    """Return all enabled regions sorted by priority.

    Returns:
        List of Region instances where enabled=True, ordered by priority ascending.
    """
    return sorted(
        (r for r in REGIONS.values() if r.enabled),
        key=lambda r: r.priority,
    )
