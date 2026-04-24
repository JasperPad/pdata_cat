"""PlayStation Store GraphQL response parser.

Core v1.0 module: extracts game data, prices, and **image links** from raw API responses.
Handles dirty/missing data gracefully with safe helper functions.
"""

from __future__ import annotations

import logging
from typing import Any

from ps5_scraper.models.game import CategoryResponse, Game, GameImage, GamePrice

logger = logging.getLogger(__name__)


class ParseError(Exception):
    """Raised when parsing fails critically."""


class PSStoreParser:
    """Parser for PlayStation Store GraphQL API responses.

    Provides methods to parse:
    - Full category responses (pageInfo + products)
    - Individual product dicts into Game models
    - Price information
    - Media/image links (v1.0 core feature)
    """

    # ─── Safe Helpers ──────────────────────────────────────────────

    @staticmethod
    def _safe_get(d: dict[str, Any] | None, *keys: str, default: Any = None) -> Any:
        """Safely get a nested value from dict. Returns default if any key missing or value is None."""
        if d is None:
            return default
        current: Any = d
        for key in keys:
            if isinstance(current, dict) and key in current:
                current = current[key]
            else:
                return default
            if current is None:
                return default
        return current

    @staticmethod
    def _safe_float(value: Any) -> float:
        """Convert value to float safely. Returns 0.0 on failure."""
        if value is None:
            return 0.0
        try:
            return float(value)
        except (ValueError, TypeError):
            return 0.0

    @staticmethod
    def _safe_int(value: Any) -> int:
        """Convert value to int safely. Returns 0 on failure."""
        if value is None:
            return 0
        try:
            return int(value)
        except (ValueError, TypeError):
            return 0

    @staticmethod
    def _safe_str(value: Any) -> str:
        """Convert value to str safely. Returns empty string on None."""
        if value is None:
            return ""
        return str(value)

    # ─── Public API ─────────────────────────────────────────────────

    def parse_category_response(self, raw_json: dict[str, Any]) -> CategoryResponse:
        """Parse full category listing response into CategoryResponse.

        Args:
            raw_json: Raw JSON dict from the API.

        Returns:
            Parsed CategoryResponse with games list.
        """
        category_data = self._safe_get(
            raw_json, "data", "categoryGridRetrieve"
        )
        if category_data is None:
            raise ParseError(
                "Invalid response: missing data.categoryGridRetrieve"
            )

        page_info = self._safe_get(category_data, "pageInfo", default={})
        products_raw = self._safe_get(category_data, "products", default=[])

        games = [self.parse_product(p) for p in products_raw]

        return CategoryResponse(
            total_count=self._safe_int(self._safe_get(page_info, "totalCount")),
            offset=self._safe_int(self._safe_get(page_info, "offset")),
            size=self._safe_int(self._safe_get(page_info, "size")),
            is_last=bool(self._safe_get(page_info, "isLast", default=True)),
            games=games,
        )

    def parse_product(self, product_dict: dict[str, Any]) -> Game:
        """Parse a single product dict from the API into a Game model.

        Args:
            product_dict: Raw product dict from API response.

        Returns:
            Populated Game model.
        """
        star_rating = self._safe_get(product_dict, "starRating", default={})

        price_raw = self._safe_get(product_dict, "price")
        media_raw = self._safe_get(product_dict, "media")
        skus_raw = self._safe_get(product_dict, "skus")

        return Game(
            id=self._safe_str(product_dict.get("id")),
            name=self._safe_str(product_dict.get("name")),
            platforms=self._safe_get(product_dict, "platforms", default=[]),
            classification=self._safe_str(
                product_dict.get("localizedStoreDisplayClassification")
            ),
            release_date=self._safe_str(product_dict.get("releaseDate")),
            provider_name=self._safe_str(product_dict.get("providerName")),
            top_genre=self._safe_str(product_dict.get("topGenre")),
            age_rating_label=self._safe_str(
                product_dict.get("ageRatingLabel")
            ),
            star_rating_score=self._safe_float(
                self._safe_get(star_rating, "score")
            ),
            star_rating_total=self._safe_int(
                self._safe_get(star_rating, "total")
            ),
            price=self.parse_price(price_raw),
            images=self.extract_images(media_raw),
            sku_count=len(skus_raw) if isinstance(skus_raw, list) else 0,
        )

    def parse_price(self, price_dict: dict[str, Any] | None) -> GamePrice | None:
        """Parse price dict into GamePrice model.

        Args:
            price_dict: Raw price dict from API, or None.

        Returns:
            GamePrice instance, or None if no price data.
        """
        if not price_dict or not isinstance(price_dict, dict):
            return None

        return GamePrice(
            base_price=self._safe_str(price_dict.get("basePrice")),
            discounted_price=self._safe_str(
                price_dict.get("discountedPrice")
            ),
            discount_text=self._safe_str(price_dict.get("discountText")),
            is_free=bool(self._safe_get(price_dict, "isFree")),
            is_exclusive=bool(self._safe_get(price_dict, "isExclusive")),
            service_branding=self._safe_get(
                price_dict, "serviceBranding", default=[]
            ),
            upsell_text=self._safe_str(price_dict.get("upsellText")),
        )

    def extract_images(
        self, media_list: list[dict[str, Any]] | None
    ) -> list[GameImage]:
        """Extract image/video links from media array — **v1.0 CORE FEATURE**.

        Handles all media roles:
        - MASTER (main promotional image)
        - GAMEHUB_COVER_ART (cover art for game hub)
        - FOUR_BY_THREE_BANNER (4:3 aspect ratio banner)
        - PORTRAIT_BANNER (portrait orientation banner)
        - LOGO (game logo)
        - SCREENSHOT (can be multiple; each stored separately)
        - PREVIEW (type=VIDEO, not IMAGE)

        Args:
            media_list: List of media dicts from the API, or None/empty.

        Returns:
            List of GameImage objects. Empty list if no valid media.
        """
        if not media_list or not isinstance(media_list, list):
            return []

        images: list[GameImage] = []
        for item in media_list:
            if not isinstance(item, dict):
                continue

            role = self._safe_str(item.get("role"))
            type_ = self._safe_str(item.get("type")).upper() or "IMAGE"
            url = self._safe_str(item.get("url"))

            # Skip items without URL — they're useless for our purposes
            if not url:
                continue

            images.append(
                GameImage(
                    role=role,
                    type=type_,
                    url=url,
                    width=self._safe_int(item.get("width")) or None,
                    height=self._safe_int(item.get("height")) or None,
                )
            )

        return images


# ─── Module-level convenience functions ─────────────────────────────
# These allow calling without instantiating the parser class.

_parser_instance = PSStoreParser()


def parse_category_response(raw_json: dict[str, Any]) -> CategoryResponse:
    """Convenience function: parse full category response."""
    return _parser_instance.parse_category_response(raw_json)


def parse_product(product_dict: dict[str, Any]) -> Game:
    """Convenience function: parse single product."""
    return _parser_instance.parse_product(product_dict)


def parse_price(price_dict: dict[str, Any] | None) -> GamePrice | None:
    """Convenience function: parse price data."""
    return _parser_instance.parse_price(price_dict)


def extract_images(media_list: list[dict[str, Any]] | None) -> list[GameImage]:
    """Convenience function: extract images from media list."""
    return _parser_instance.extract_images(media_list)
