"""Tests for Pydantic v2 data models (Game, GamePrice, GameImage, CategoryResponse)."""

import pytest
from pydantic import ValidationError

from ps5_scraper.models.game import Game, GamePrice, GameImage, CategoryResponse


class TestGamePrice:
    """Test GamePrice model."""

    def test_create_with_all_fields(self):
        price = GamePrice(
            base_price="HK$708.00",
            discounted_price="HK$389.40",
            discount_text="-45%",
            is_free=False,
            is_exclusive=False,
            service_branding=["NONE"],
            upsell_text="省下10%",
        )
        assert price.base_price == "HK$708.00"
        assert price.discounted_price == "HK$389.40"
        assert price.discount_text == "-45%"
        assert price.is_free is False
        assert price.is_exclusive is False
        assert price.service_branding == ["NONE"]
        assert price.upsell_text == "省下10%"

    def test_default_values(self):
        price = GamePrice()
        assert price.base_price == ""
        assert price.discounted_price == ""
        assert price.discount_text == ""
        assert price.is_free is False
        assert price.is_exclusive is False
        assert price.service_branding == []
        assert price.upsell_text == ""

    def test_is_free_true(self):
        price = GamePrice(is_free=True)
        assert price.is_free is True

    def test_model_dump_serialization(self):
        price = GamePrice(base_price="HK$100", discounted_price="HK$50", discount_text="-50%")
        d = price.model_dump()
        assert d["base_price"] == "HK$100"
        assert d["discounted_price"] == "HK$50"
        assert d["discount_text"] == "-50%"
        assert d["is_free"] is False


class TestGameImage:
    """Test GameImage model."""

    def test_create_with_all_fields(self):
        img = GameImage(role="MASTER", type="IMAGE", url="https://example.com/img.jpg", width=1920, height=1080)
        assert img.role == "MASTER"
        assert img.type == "IMAGE"
        assert img.url == "https://example.com/img.jpg"
        assert img.width == 1920
        assert img.height == 1080

    def test_default_optional_fields(self):
        img = GameImage(role="SCREENSHOT", type="IMAGE", url="https://example.com/ss.jpg")
        assert img.width is None
        assert img.height is None

    def test_video_type(self):
        img = GameImage(role="PREVIEW", type="VIDEO", url="https://example.com/vid.mp4")
        assert img.type == "VIDEO"

    def test_model_dump(self):
        img = GameImage(role="LOGO", type="IMAGE", url="https://example.com/logo.png")
        d = img.model_dump()
        assert d["role"] == "LOGO"
        assert d["type"] == "IMAGE"
        assert d["url"] == "https://example.com/logo.png"
        assert d["width"] is None
        assert d["height"] is None


class TestGame:
    """Test Game model."""

    def test_create_with_all_fields(self):
        price = GamePrice(base_price="HK$708.00", discounted_price="HK$389.40")
        images = [
            GameImage(role="MASTER", type="IMAGE", url="https://example.com/master.jpg"),
            GameImage(role="SCREENSHOT", type="IMAGE", url="https://example.com/ss1.jpg"),
        ]
        game = Game(
            id="HP9000-PPSA13198_00-STELLARBLADECE00",
            name="劍星",
            platforms=["PS5"],
            classification="正式版遊戲",
            release_date="2024-04-26",
            providerName="SHIFT UP",
            top_genre="動作",
            age_rating_label="18+",
            star_rating_score=4.5,
            star_rating_total=1234,
            price=price,
            images=images,
            sku_count=1,
            last_updated=1713964800,
        )
        assert game.id == "HP9000-PPSA13198_00-STELLARBLADECE00"
        assert game.name == "劍星"
        assert game.platforms == ["PS5"]
        assert game.classification == "正式版遊戲"
        assert game.release_date == "2024-04-26"
        assert game.top_genre == "動作"
        assert game.age_rating_label == "18+"
        assert game.star_rating_score == 4.5
        assert game.star_rating_total == 1234
        assert game.price is not None
        assert game.price.base_price == "HK$708.00"
        assert len(game.images) == 2
        assert game.sku_count == 1
        assert game.last_updated == 1713964800

    def test_default_values(self):
        game = Game(id="test-id", name="Test Game")
        assert game.platforms == []
        assert game.classification == ""
        assert game.release_date == ""
        assert game.provider_name == ""
        assert game.top_genre == ""
        assert game.age_rating_label == ""
        assert game.star_rating_score == 0.0
        assert game.star_rating_total == 0
        assert game.price is None
        assert game.images == []
        assert game.sku_count == 0
        assert game.last_updated == 0

    def test_price_none_works(self):
        """price=None should be accepted and work normally."""
        game = Game(id="test-id", name="Test Game", price=None)
        assert game.price is None
        # serialization should handle None price
        d = game.model_dump()
        assert d["price"] is None

    def test_empty_images_list(self):
        game = Game(id="test-id", name="Test Game", images=[])
        assert game.images == []
        assert len(game.images) == 0

    def test_model_dump_serialization(self):
        game = Game(
            id="test-001",
            name="Test Game",
            platforms=["PS5"],
            star_rating_score=4.5,
            star_rating_total=100,
            price=GamePrice(base_price="HK$100"),
            images=[GameImage(role="MASTER", type="IMAGE", url="https://img.jpg")],
        )
        d = game.model_dump()
        assert d["id"] == "test-001"
        assert d["name"] == "Test Game"
        assert d["platforms"] == ["PS5"]
        assert d["star_rating_score"] == 4.5
        assert isinstance(d["price"], dict)
        assert d["price"]["base_price"] == "HK$100"
        assert len(d["images"]) == 1
        assert d["images"][0]["role"] == "MASTER"

    def test_id_required(self):
        """id is required field."""
        with pytest.raises(ValidationError):
            Game(name="Test")

    def test_name_required(self):
        """name is required field."""
        with pytest.raises(ValidationError):
            Game(id="test-id")


class TestCategoryResponse:
    """Test CategoryResponse model."""

    def test_create_with_data(self):
        games = [Game(id="g1", name="Game 1"), Game(id="g2", name="Game 2")]
        resp = CategoryResponse(
            total_count=7047,
            offset=0,
            size=24,
            is_last=False,
            games=games,
        )
        assert resp.total_count == 7047
        assert resp.offset == 0
        assert resp.size == 24
        assert resp.is_last is False
        assert len(resp.games) == 2
        assert resp.games[0].id == "g1"

    def test_empty_games_list(self):
        resp = CategoryResponse(total_count=0, offset=0, size=24, is_last=True, games=[])
        assert resp.total_count == 0
        assert resp.games == []
        assert resp.is_last is True

    def test_model_dump(self):
        resp = CategoryResponse(total_count=100, offset=0, size=10, is_last=False, games=[Game(id="g1", name="G")])
        d = resp.model_dump()
        assert d["total_count"] == 100
        assert d["offset"] == 0
        assert d["size"] == 10
        assert d["is_last"] is False
        assert len(d["games"]) == 1
