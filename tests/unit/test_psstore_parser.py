"""Tests for PSStoreParser: API response parsing with multi-region support."""

import pytest

from ps5_scraper.api.psstore_parser import PSStoreParser, parse_product
from ps5_scraper.models.game import Game


# ─── Fixtures ──────────────────────────────────────────────────────

SAMPLE_PRODUCT = {
    "id": "HP9000-PPSA13198_00-STELLARBLADECE00",
    "name": "劍星",
    "platforms": ["PS5"],
    "localizedStoreDisplayClassification": "正式版遊戲",
    "releaseDate": "2024-04-26",
    "providerName": "SHIFT UP",
    "topGenre": "動作",
    "ageRatingLabel": "18+",
    "starRating": {"score": 4.5, "total": 1234},
    "price": {
        "basePrice": "HK$708.00",
        "discountedPrice": "HK$389.40",
        "discountText": "-45%",
        "isFree": False,
        "isExclusive": False,
        "serviceBranding": ["NONE"],
        "upsellText": "省下10%",
    },
    "media": [
        {"role": "MASTER", "type": "IMAGE", "url": "https://img.master.jpg", "width": 1920, "height": 1080},
        {"role": "SCREENSHOT", "type": "IMAGE", "url": "https://img.ss1.jpg", "width": 1280, "height": 720},
    ],
    "skus": [{"id": "sku-1"}, {"id": "sku-2"}],
}


class TestParseProduct:
    """Test single product parsing."""

    def test_parse_basic_fields(self):
        """Basic fields should be extracted correctly."""
        game = PSStoreParser().parse_product(SAMPLE_PRODUCT)
        assert game.id == "HP9000-PPSA13198_00-STELLARBLADECE00"
        assert game.name == "劍星"
        assert game.platforms == ["PS5"]
        assert game.classification == "正式版遊戲"
        assert game.release_date == "2024-04-26"
        assert game.provider_name == "SHIFT UP"

    def test_parse_price(self):
        """Price should be parsed into GamePrice."""
        game = PSStoreParser().parse_product(SAMPLE_PRODUCT)
        assert game.price is not None
        assert game.price.base_price == "HK$708.00"
        assert game.price.discounted_price == "HK$389.40"
        assert game.price.is_free is False

    def test_parse_images(self):
        """Images should be extracted from media list."""
        game = PSStoreParser().parse_product(SAMPLE_PRODUCT)
        assert len(game.images) == 2
        roles = {img.role for img in game.images}
        assert "MASTER" in roles
        assert "SCREENSHOT" in roles

    def test_parse_sku_count(self):
        """SKU count should reflect number of SKUs."""
        game = PSStoreParser().parse_product(SAMPLE_PRODUCT)
        assert game.sku_count == 2

    def test_parse_star_rating(self):
        """Star rating score and total should be parsed."""
        game = PSStoreParser().parse_product(SAMPLE_PRODUCT)
        assert game.star_rating_score == 4.5
        assert game.star_rating_total == 1234


class TestRegionInjection:
    """Test that Parser injects region into parsed Game objects."""

    def test_default_region_is_hk(self):
        """Default parser (no region arg) should use HK."""
        game = PSStoreParser().parse_product(SAMPLE_PRODUCT)
        assert game.region == "HK"

    def test_explicit_us_region(self):
        """Parser configured for US should set region=US."""
        parser = PSStoreParser(region="US")
        game = parser.parse_product(SAMPLE_PRODUCT)
        assert game.region == "US"

    def test_explicit_jp_region(self):
        """Parser configured for JP should set region=JP."""
        parser = PSStoreParser(region="JP")
        game = parser.parse_product(SAMPLE_PRODUCT)
        assert game.region == "JP"

    def test_explicit_kr_region(self):
        """Parser configured for KR should set region=KR."""
        parser = PSStoreParser(region="KR")
        game = parser.parse_product(SAMPLE_PRODUCT)
        assert game.region == "KR"

    def test_multiple_products_same_region(self):
        """All products from same parser instance share the same region."""
        parser = PSStoreParser(region="EU")
        g1 = parser.parse_product(SAMPLE_PRODUCT)
        g2 = parser.parse_product({
            **SAMPLE_PRODUCT,
            "id": "ANOTHER-GAME-ID",
            "name": "Another Game",
        })
        assert g1.region == "EU"
        assert g2.region == "EU"


class TestEdgeCases:
    """Test parsing edge cases."""

    def test_missing_optional_fields(self):
        """Missing optional fields should not crash."""
        minimal = {"id": "minimal-id", "name": "Minimal"}
        game = PSStoreParser(region="TW").parse_product(minimal)
        assert game.id == "minimal-id"
        assert game.name == "Minimal"
        assert game.region == "TW"
        assert game.platforms == []
        assert game.images == []

    def test_empty_media_list(self):
        """Empty media list should produce empty images list."""
        product = {**SAMPLE_PRODUCT, "media": []}
        game = PSStoreParser().parse_product(product)
        assert game.images == []

    def test_none_price(self):
        """None price should result in None price field."""
        product = {**SAMPLE_PRODUCT, "price": None}
        game = PSStoreParser().parse_product(product)
        assert game.price is None
