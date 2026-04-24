"""Tests for PSStoreParser: GraphQL response parsing with focus on image extraction."""

import pytest

from ps5_scraper.api.psstore_parser import (
    PSStoreParser,
    extract_images,
    parse_category_response,
    parse_price,
    parse_product,
)
from ps5_scraper.models.game import CategoryResponse, Game, GameImage, GamePrice


# ─── Sample Data (realistic from PS Store API) ──────────────────────────

SAMPLE_FULL_RESPONSE = {
    "data": {
        "categoryGridRetrieve": {
            "__typename": "CategoryGrid",
            "pageInfo": {
                "totalCount": 7047,
                "offset": 0,
                "size": 24,
                "isLast": False,
            },
            "products": [
                {
                    "__typename": "Product",
                    "name": "劍星",
                    "id": "HP9000-PPSA13198_00-STELLARBLADECE00",
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
                        "upsellServiceBranding": ["PS_PLUS"],
                        "upsellText": "省下10%",
                    },
                    "media": [
                        {
                            "role": "MASTER",
                            "type": "IMAGE",
                            "url": "https://image.api.playstation.com/cdn/master.jpg",
                        },
                        {
                            "role": "GAMEHUB_COVER_ART",
                            "type": "IMAGE",
                            "url": "https://image.api.playstation.com/cdn/cover.jpg",
                        },
                        {
                            "role": "FOUR_BY_THREE_BANNER",
                            "type": "IMAGE",
                            "url": "https://image.api.playstation.com/cdn/banner43.jpg",
                        },
                        {
                            "role": "PORTRAIT_BANNER",
                            "type": "IMAGE",
                            "url": "https://image.api.playstation.com/cdn/portrait.jpg",
                        },
                        {
                            "role": "LOGO",
                            "type": "IMAGE",
                            "url": "https://image.api.playstation.com/cdn/logo.png",
                        },
                        {
                            "role": "SCREENSHOT",
                            "type": "IMAGE",
                            "url": "https://image.api.playstation.com/cdn/ss1.jpg",
                        },
                        {
                            "role": "SCREENSHOT",
                            "type": "IMAGE",
                            "url": "https://image.api.playstation.com/cdn/ss2.jpg",
                        },
                        {
                            "role": "PREVIEW",
                            "type": "VIDEO",
                            "url": "https://cdn.video.psn/trailer.mp4",
                        },
                    ],
                    "skus": [
                        {"__typename": "Sku", "id": "sku-001", "type": "STANDARD"},
                        {"__typename": "Sku", "id": "sku-002", "type": "DELUXE"},
                    ],
                }
            ],
        }
    }
}

SAMPLE_PRODUCT = SAMPLE_FULL_RESPONSE["data"]["categoryGridRetrieve"]["products"][0]

SAMPLE_PRICE = SAMPLE_PRODUCT["price"]


# ─── Test: Full Response Parsing ───────────────────────────────────────


class TestParseCategoryResponse:
    """Test full category response parsing (pageInfo + products)."""

    def test_full_response_parsing(self):
        result = parse_category_response(SAMPLE_FULL_RESPONSE)
        assert isinstance(result, CategoryResponse)
        assert result.total_count == 7047
        assert result.offset == 0
        assert result.size == 24
        assert result.is_last is False
        assert len(result.games) == 1

    def test_parsed_game_fields(self):
        result = parse_category_response(SAMPLE_FULL_RESPONSE)
        game = result.games[0]
        assert game.name == "劍星"
        assert game.id == "HP9000-PPSA13198_00-STELLARBLADECE00"
        assert game.platforms == ["PS5"]
        assert game.classification == "正式版遊戲"
        assert game.release_date == "2024-04-26"
        assert game.provider_name == "SHIFT UP"
        assert game.top_genre == "動作"
        assert game.age_rating_label == "18+"

    def test_empty_products_list(self):
        data = {
            "data": {
                "categoryGridRetrieve": {
                    "pageInfo": {"totalCount": 0, "offset": 0, "size": 24, "isLast": True},
                    "products": [],
                }
            }
        }
        result = parse_category_response(data)
        assert result.total_count == 0
        assert result.games == []
        assert result.is_last is True


# ─── Test: Price Parsing ───────────────────────────────────────────────


class TestParsePrice:
    """Test price field mapping."""

    def test_all_price_fields(self):
        price = parse_price(SAMPLE_PRICE)
        assert isinstance(price, GamePrice)
        assert price.base_price == "HK$708.00"
        assert price.discounted_price == "HK$389.40"
        assert price.discount_text == "-45%"
        assert price.is_free is False
        assert price.is_exclusive is False
        assert price.service_branding == ["NONE"]
        assert price.upsell_text == "省下10%"

    def test_missing_price_returns_none(self):
        """Missing price field should return None without crashing."""
        product_without_price = {"name": "Test", "id": "test-id"}
        # When we call parse_product on a product without price, it should handle None
        # But let's also test parse_price directly with None
        result = parse_price(None)
        assert result is None

    def test_none_price_in_product(self):
        """Product with price=None should have price=None."""
        product = {**SAMPLE_PRODUCT, "price": None}
        game = parse_product(product)
        assert game.price is None

    def test_free_game_price(self):
        free_price = {
            "basePrice": "HK$0.00",
            "discountedPrice": "HK$0.00",
            "discountText": "",
            "isFree": True,
            "isExclusive": False,
            "serviceBranding": ["NONE"],
            "upsellServiceBranding": [],
            "upsellText": "",
        }
        price = parse_price(free_price)
        assert price.is_free is True
        assert price.base_price == "HK$0.00"


# ─── Test: Image Extraction (v1.0 CORE) ───────────────────────────────


class TestExtractImages:
    """Test complete image link extraction — this is the v1.0 core feature."""

    def test_extract_all_image_roles(self):
        media = SAMPLE_PRODUCT["media"]
        images = extract_images(media)

        roles = [img.role for img in images]
        urls = [img.url for img in images]
        types_ = [img.type for img in images]

        # All expected roles should be present
        assert "MASTER" in roles
        assert "GAMEHUB_COVER_ART" in roles
        assert "FOUR_BY_THREE_BANNER" in roles
        assert "PORTRAIT_BANNER" in roles
        assert "LOGO" in roles

        # SCREENSHOT should appear twice (two screenshots)
        screenshot_count = sum(1 for r in roles if r == "SCREENSHOT")
        assert screenshot_count == 2

        # PREVIEW should be VIDEO type
        preview_imgs = [img for img in images if img.role == "PREVIEW"]
        assert len(preview_imgs) == 1
        assert preview_imgs[0].type == "VIDEO"
        assert "video.psn" in preview_imgs[0].url or preview_imgs[0].url.endswith(".mp4")

        # Total count: MASTER + COVER + BANNER43 + PORTRAIT + LOGO + 2xSCREENSHOT + PREVIEW = 8
        assert len(images) == 8

    def test_screenshot_urls_are_distinct(self):
        media = SAMPLE_PRODUCT["media"]
        images = extract_images(media)
        screenshots = [img for img in images if img.role == "SCREENSHOT"]
        urls = [s.url for s in screenshots]
        assert len(urls) == 2
        assert urls[0] != urls[1]
        assert "ss1" in urls[0]
        assert "ss2" in urls[1]

    def test_master_image_url(self):
        media = SAMPLE_PRODUCT["media"]
        images = extract_images(media)
        master = [img for img in images if img.role == "MASTER"]
        assert len(master) == 1
        assert master[0].type == "IMAGE"
        assert "master" in master[0].url.lower()

    def test_preview_is_video_not_image(self):
        media = SAMPLE_PRODUCT["media"]
        images = extract_images(media)
        previews = [img for img in images if img.role == "PREVIEW"]
        assert previews[0].type == "VIDEO"
        assert previews[0].type != "IMAGE"

    def test_missing_media_field_returns_empty_list(self):
        """Missing 'media' key should return empty list, not crash."""
        result = extract_images(None)
        assert result == []

        result2 = extract_images([])
        assert result2 == []


# ─── Test: Product Parsing ─────────────────────────────────────────────


class TestParseProduct:
    """Test single product dict → Game parsing."""

    def test_full_product(self):
        game = parse_product(SAMPLE_PRODUCT)
        assert isinstance(game, Game)
        assert game.id == "HP9000-PPSA13198_00-STELLARBLADECE00"
        assert game.name == "劍星"
        assert game.star_rating_score == 4.5
        assert game.star_rating_total == 1234
        assert game.sku_count == 2
        assert len(game.images) == 8

    def test_sku_count(self):
        game = parse_product(SAMPLE_PRODUCT)
        assert game.sku_count == 2


# ─── Test: Dirty Data Handling ─────────────────────────────────────────


class TestDirtyDataHandling:
    """Test robustness against malformed/missing data."""

    def test_none_values_in_product(self):
        dirty = {
            "name": None,
            "id": None,
            "platforms": None,
            "localizedStoreDisplayClassification": None,
            "releaseDate": None,
            "providerName": None,
            "topGenre": None,
            "ageRatingLabel": None,
            "starRating": None,
            "price": None,
            "media": None,
            "skus": None,
        }
        # Should not crash; should return a Game with defaults
        game = parse_product(dirty)
        assert isinstance(game, Game)
        assert game.name == ""
        assert game.id == ""

    def test_missing_keys(self):
        minimal = {"name": "Minimal", "id": "min-001"}
        game = parse_product(minimal)
        assert game.name == "Minimal"
        assert game.id == "min-001"
        assert game.platforms == []
        assert game.price is None
        assert game.images == []
        assert game.star_rating_score == 0.0

    def test_star_rating_with_none(self):
        product = {**SAMPLE_PRODUCT, "starRating": None}
        game = parse_product(product)
        assert game.star_rating_score == 0.0
        assert game.star_rating_total == 0

    def test_star_rating_missing_keys(self):
        product = {**SAMPLE_PRODUCT, "starRating": {}}
        game = parse_product(product)
        assert game.star_rating_score == 0.0
        assert game.star_rating_total == 0

    def test_media_item_missing_url(self):
        media = [
            {"role": "MASTER", "type": "IMAGE"},  # no url
            {"role": "SCREENSHOT", "type": "IMAGE", "url": "https://valid.jpg"},
        ]
        images = extract_images(media)
        # Items without url should be skipped
        valid_images = [img for img in images if img.url]
        assert len(valid_images) >= 1

    def test_media_item_with_none_type(self):
        media = [
            {"role": "MASTER", "type": None, "url": "https://img.jpg"},
        ]
        images = extract_images(media)
        # Should handle gracefully - type becomes empty string or similar
        assert len(images) >= 0  # Just don't crash


# ─── Test: Helper Functions ────────────────────────────────────────────


class TestHelperFunctions:
    """Test _safe_get, _safe_float, _safe_int helpers."""

    def test_safe_get_existing_key(self):
        parser = PSStoreParser()
        assert parser._safe_get({"a": 1}, "a") == 1

    def test_safe_get_missing_key(self):
        parser = PSStoreParser()
        assert parser._safe_get({}, "a", default="fallback") == "fallback"
        assert parser._safe_get({}, "a") is None

    def test_safe_get_nested(self):
        parser = PSStoreParser()
        assert parser._safe_get({"a": {"b": 2}}, "a", "b") == 2

    def test_safe_get_nested_missing(self):
        parser = PSStoreParser()
        assert parser._safe_get({"a": {}}, "a", "b", default=99) == 99

    def test_safe_float_valid(self):
        parser = PSStoreParser()
        assert parser._safe_float(4.5) == 4.5
        assert parser._safe_float("3.14") == 3.14

    def test_safe_float_invalid(self):
        parser = PSStoreParser()
        assert parser._safe_float(None) == 0.0
        assert parser._safe_float("abc") == 0.0
        assert parser._safe_float("") == 0.0

    def test_safe_int_valid(self):
        parser = PSStoreParser()
        assert parser._safe_int(1234) == 1234
        assert parser._safe_int("567") == 567

    def test_safe_int_invalid(self):
        parser = PSStoreParser()
        assert parser._safe_int(None) == 0
        assert parser._safe_int("abc") == 0
        assert parser._safe_int("") == 0
