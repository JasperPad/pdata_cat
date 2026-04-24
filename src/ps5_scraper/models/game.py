"""Pydantic v2 data models for PS5 HK Scraper."""

from __future__ import annotations

from pydantic import BaseModel, Field


class GamePrice(BaseModel):
    """Price information for a game."""

    base_price: str = ""
    discounted_price: str = ""
    discount_text: str = ""
    is_free: bool = False
    is_exclusive: bool = False
    service_branding: list[str] = []
    upsell_text: str = ""


class GameImage(BaseModel):
    """Image or video media for a game."""

    role: str
    type: str  # "IMAGE" or "VIDEO"
    url: str
    width: int | None = None
    height: int | None = None


class Game(BaseModel):
    """Game data model representing a PS Store product."""

    id: str
    name: str
    platforms: list[str] = []
    classification: str = ""
    release_date: str = ""
    provider_name: str = ""
    top_genre: str = ""
    age_rating_label: str = ""
    star_rating_score: float = 0.0
    star_rating_total: int = 0
    price: GamePrice | None = None
    images: list[GameImage] = []
    sku_count: int = 0
    last_updated: int = 0


class CategoryResponse(BaseModel):
    """Response from category listing API."""

    total_count: int
    offset: int
    size: int
    is_last: bool
    games: list[Game]
