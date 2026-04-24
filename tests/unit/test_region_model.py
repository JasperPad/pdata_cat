"""Tests for the Region model (v2.0 multi-region architecture)."""

from __future__ import annotations

import pytest

from ps5_scraper.models.region import Region, REGIONS, get_region, get_enabled_regions


class TestRegionModel:
    """Region Pydantic model validation tests."""

    def test_region_creation_minimal(self) -> None:
        """Region can be created with required fields only."""
        region = Region(code="HK", locale="zh-hant-hk", currency="HKD", name="港服")
        assert region.code == "HK"
        assert region.locale == "zh-hant-hk"
        assert region.currency == "HKD"
        assert region.name == "港服"

    def test_region_default_values(self) -> None:
        """Region has sensible defaults for optional fields."""
        region = Region(code="US", locale="en-us", currency="USD", name="美服")
        assert region.language == ""
        assert region.enabled is True
        assert region.priority == 0

    def test_region_all_fields(self) -> None:
        """Region accepts all fields."""
        region = Region(
            code="JP",
            locale="ja-jp",
            currency="JPY",
            name="日服",
            language="ja",
            enabled=True,
            priority=2,
        )
        assert region.language == "ja"
        assert region.enabled is True
        assert region.priority == 2

    def test_region_code_required(self) -> None:
        """code field is required."""
        with pytest.raises(Exception):
            Region(locale="en-us", currency="USD", name="US")  # type: ignore[call-arg]

    def test_locale_required(self) -> None:
        """locale field is required."""
        with pytest.raises(Exception):
            Region(code="US", currency="USD", name="US")  # type: ignore[call-arg]

    def test_currency_required(self) -> None:
        """currency field is required."""
        with pytest.raises(Exception):
            Region(code="US", locale="en-us", name="US")  # type: ignore[call-arg]

    def test_name_required(self) -> None:
        """name field is required."""
        with pytest.raises(Exception):
            Region(code="US", locale="en-us", currency="USD")  # type: ignore[call-arg]

    def test_region_serialization(self) -> None:
        """Region can be serialized to dict and back."""
        region = Region(code="TW", locale="zh-hant-tw", currency="TWD", name="台服")
        d = region.model_dump()
        restored = Region(**d)
        assert restored.code == region.code
        assert restored.locale == region.locale
        assert restored.currency == region.currency
        assert restored.name == region.name


class TestPredefinedRegions:
    """Tests for the built-in REGIONS dictionary."""

    def test_regions_is_not_empty(self) -> None:
        """REGIONS dict should have entries."""
        assert len(REGIONS) > 0

    def test_hk_region_exists(self) -> None:
        """Hong Kong region (default) must exist."""
        assert "HK" in REGIONS
        hk = REGIONS["HK"]
        assert hk.locale == "zh-hant-hk"
        assert hk.currency == "HKD"
        assert hk.name == "港服"

    def test_us_region_exists(self) -> None:
        """US region (largest catalog) must exist."""
        assert "US" in REGIONS
        us = REGIONS["US"]
        assert us.locale == "en-us"
        assert us.currency == "USD"
        assert us.name == "美服"

    def test_jp_region_exists(self) -> None:
        """Japan region must exist."""
        assert "JP" in REGIONS
        jp = REGIONS["JP"]
        assert jp.locale == "ja-jp"
        assert jp.currency == "JPY"

    def test_all_regions_have_valid_locale_format(self) -> None:
        """All predefined regions should have xx-xx locale format."""
        for code, region in REGIONS.items():
            assert "-" in region.locale, f"Region {code} has invalid locale format: {region.locale}"

    def test_all_regions_have_3_letter_currency(self) -> None:
        """All predefined regions should have ISO 4217 currency codes (3 letters)."""
        for code, region in REGIONS.items():
            assert len(region.currency) == 3 and region.currency.isalpha(), \
                f"Region {code} has invalid currency: {region.currency}"


class TestRegionHelpers:
    """Tests for module-level helper functions."""

    def test_get_region_existing(self) -> None:
        """get_region returns the correct region for a valid code (case-insensitive)."""
        region = get_region("hk")  # lowercase input → uppercase lookup
        assert region is not None
        assert region.code == "HK"  # returns UPPERCASE
        assert region.currency == "HKD"

    def test_get_region_case_insensitive(self) -> None:
        """get_region handles mixed-case input."""
        r1 = get_region("us")
        r2 = get_region("Us")
        r3 = get_region("US")
        assert r1 is not None and r2 is not None and r3 is not None
        assert r1.code == r2.code == r3.code == "US"

    def test_get_region_missing(self) -> None:
        """get_region returns None for an unknown code."""
        result = get_region("XX_NONEXISTENT")
        assert result is None

    def test_get_enabled_regions_filters_disabled(self) -> None:
        """get_enabled_regions excludes disabled regions."""
        enabled = get_enabled_regions()
        # At minimum, HK, US, JP should be enabled (UPPERCASE)
        codes = {r.code for r in enabled}
        assert "HK" in codes
        assert "US" in codes
        # All returned regions should be enabled=True
        for r in enabled:
            assert r.enabled is True

    def test_get_enabled_regions_excludes_cn(self) -> None:
        """get_enabled_regions should exclude CN (disabled) region."""
        enabled = get_enabled_regions()
        cn_codes = [r.code for r in enabled if r.code == "CN"]
        assert len(cn_codes) == 0, "CN region should be filtered out"

    def test_get_enabled_regions_returns_list(self) -> None:
        """get_enabled_regions returns a list sorted by priority."""
        enabled = get_enabled_regions()
        assert isinstance(enabled, list)
        if len(enabled) > 1:
            priorities = [r.priority for r in enabled]
            assert priorities == sorted(priorities), "Regions should be sorted by priority"


class TestRegionEdgeCases:
    """Edge case tests for Region model."""

    def test_disabled_region(self) -> None:
        """Disabled regions are still valid Region objects."""
        cn = Region(
            code="CN",
            locale="zh-cn",
            currency="CNY",
            name="国服",
            enabled=False,
            priority=99,
        )
        assert cn.enabled is False

    def test_region_code_uppercase_convention(self) -> None:
        """All predefined region codes follow UPPERCASE convention."""
        for code in REGIONS:
            assert code == code.upper(), f"Region key '{code}' should be UPPERCASE"
            assert REGIONS[code].code == code, f"Region .code should match key"

    def test_empty_name_allowed(self) -> None:
        """Empty string is allowed for name (though not recommended)."""
        region = Region(code="XX", locale="xx-xx", currency="XXX", name="")
        assert region.name == ""
