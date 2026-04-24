"""CRUD repository layer for games and images in SQLite.

Provides:
- GameRepository: upsert/get/delete/count for games
- Image management: upsert_images / get_images with deduplication
- merge_data: smart field merging for updates
"""

from __future__ import annotations

import json
import logging
from typing import Any

from ps5_scraper.models.game import Game, GameImage, GamePrice
from ps5_scraper.storage.database import DatabaseManager

logger = logging.getLogger(__name__)


def merge_data(existing: Game, new: Game) -> Game:
    """Merge new data into existing game, preserving non-default values.

    Strategy: For each field, use the new value if it's not a default/empty value,
    otherwise keep the existing value. This prevents blanking out data when
    partial updates come in.

    Args:
        existing: The current game record from DB.
        new: The incoming game data (potentially partial).

    Returns:
        Merged Game instance.
    """
    # Build merged data by choosing non-default values from `new`
    merged_dict = existing.model_dump()

    new_dict = new.model_dump()

    # Fields where we always take the new value (these are "always update" fields)
    always_update = {"name", "price", "images", "last_updated", "sku_count"}

    for key, new_value in new_dict.items():
        if key in always_update:
            # Always update these fields from new data
            merged_dict[key] = new_value
        elif key == "platforms":
            # Use new platforms if non-empty, else keep existing
            merged_dict[key] = new_value if new_value else merged_dict.get(key, [])
        elif key in ("star_rating_score", "star_rating_total"):
            # Update ratings only if new value is non-zero (meaningful update)
            if new_value != 0 and new_value is not None:
                merged_dict[key] = new_value
        elif isinstance(new_value, str):
            # For string fields: use new value if non-empty
            if new_value:
                merged_dict[key] = new_value
        elif new_value is not None and new_value != []:
            # Non-string, non-list fields with meaningful data
            merged_dict[key] = new_value

    return Game(**merged_dict)


class GameRepository:
    """CRUD repository for Game entities.

    Handles persistence of Game and GameImage models to SQLite.
    Uses INSERT OR REPLACE for upserts (by game id).
    Images are managed separately with batch operations.
    """

    def __init__(self, db_manager: DatabaseManager) -> None:
        self.db = db_manager

    def upsert(self, game: Game) -> None:
        """Insert or replace a game record.

        Also handles image storage via upsert_images.

        Args:
            game: The game to persist.
        """
        price = game.price
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO games (
                    id, name, platforms, classification, release_date,
                    provider_name, top_genre, age_rating_label,
                    star_rating_score, star_rating_total,
                    base_price, discounted_price, discount_text,
                    is_free, is_exclusive, service_branding,
                    upsell_text, sku_count, last_updated
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                game.id,
                game.name,
                json.dumps(game.platforms, ensure_ascii=False),
                game.classification,
                game.release_date,
                game.provider_name,
                game.top_genre,
                game.age_rating_label,
                game.star_rating_score,
                game.star_rating_total,
                price.base_price if price else "",
                price.discounted_price if price else "",
                price.discount_text if price else "",
                1 if price and price.is_free else 0,
                1 if price and price.is_exclusive else 0,
                json.dumps(price.service_branding, ensure_ascii=False) if price else "[]",
                price.upsell_text if price else "",
                game.sku_count,
                game.last_updated,
            ))

        # Upsert images after game is saved
        self.upsert_images(game.id, game.images)

    def get_by_id(self, game_id: str) -> Game | None:
        """Retrieve a single game by its ID.

        Args:
            game_id: The game's unique identifier.

        Returns:
            Game instance, or None if not found.
        """
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM games WHERE id = ?", (game_id,))
            row = cursor.fetchone()

        if row is None:
            return None

        return self._row_to_game(row)

    def get_all(
        self, limit: int = 100, offset: int = 0
    ) -> list[Game]:
        """Retrieve multiple games with pagination.

        Args:
            limit: Maximum number of results.
            offset: Number of records to skip.

        Returns:
            List of Game instances.
        """
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM games ORDER BY last_updated DESC LIMIT ? OFFSET ?",
                (limit, offset),
            )
            rows = cursor.fetchall()

        return [self._row_to_game(row) for row in rows]

    def get_count(self) -> int:
        """Get total number of games in the database."""
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM games")
            return cursor.fetchone()[0]

    def delete_game(self, game_id: str) -> None:
        """Delete a game and cascade-delete its images.

        Args:
            game_id: The game's unique identifier.
        """
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM game_images WHERE game_id = ?", (game_id,))
            cursor.execute("DELETE FROM games WHERE id = ?", (game_id,))

    # ─── Image Management ──────────────────────────────────────────

    def upsert_images(
        self, game_id: str, images: list[GameImage]
    ) -> None:
        """Batch insert/update images for a game.

        Strategy: delete all existing images for this game, then insert new ones.
        This ensures image lists are always in sync with the latest data.

        Args:
            game_id: The parent game's ID.
            images: List of GameImage objects to store.
        """
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            # Delete existing images for this game
            cursor.execute("DELETE FROM game_images WHERE game_id = ?", (game_id,))
            
            # Insert new images
            if images:
                for img in images:
                    cursor.execute("""
                        INSERT OR IGNORE INTO game_images
                            (game_id, role, image_type, url, width, height)
                        VALUES (?, ?, ?, ?, ?, ?)
                    """, (
                        game_id,
                        img.role,
                        img.type,
                        img.url,
                        img.width,
                        img.height,
                    ))

    def get_images(self, game_id: str) -> list[GameImage]:
        """Retrieve all images for a game.

        Args:
            game_id: The parent game's ID.

        Returns:
            List of GameImage objects.
        """
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT role, image_type, url, width, height "
                "FROM game_images WHERE game_id = ? ORDER BY id",
                (game_id,),
            )
            rows = cursor.fetchall()

        return [
            GameImage(
                role=row[0],
                type=row[1],
                url=row[2],
                width=row[3],
                height=row[4],
            )
            for row in rows
        ]

    # ─── Private Helpers ───────────────────────────────────────────

    @staticmethod
    def _row_to_game(row: tuple[Any, ...]) -> Game:
        """Convert a database row tuple to a Game model.

        Row order matches CREATE TABLE statement column order.
        """
        # Unpack row: id(0), name(1), platforms(2), classification(3),
        #   release_date(4), provider_name(5), top_genre(6), age_rating_label(7),
        #   star_rating_score(8), star_rating_total(9), base_price(10),
        #   discounted_price(11), discount_text(12), is_free(13), is_exclusive(14),
        #   service_branding(15), upsell_text(16), sku_count(17), last_updated(18),
        #   created_at(19), updated_at(20)

        has_price = row[10] or bool(row[12]) or row[13] == 1 or row[14] == 1

        price = None
        if has_price:
            price = GamePrice(
                base_price=row[10] or "",
                discounted_price=row[11] or "",
                discount_text=row[12] or "",
                is_free=bool(row[13]),
                is_exclusive=bool(row[14]),
                service_branding=json.loads(row[15]) if row[15] else [],
                upsell_text=row[16] or "",
            )

        return Game(
            id=row[0],
            name=row[1],
            platforms=json.loads(row[2]) if row[2] else [],
            classification=row[3] or "",
            release_date=row[4] or "",
            provider_name=row[5] or "",
            top_genre=row[6] or "",
            age_rating_label=row[7] or "",
            star_rating_score=row[8] if row[8] is not None else 0.0,
            star_rating_total=row[9] if row[9] is not None else 0,
            price=price,
            images=[],  # Loaded separately via get_images()
            sku_count=row[17] if row[17] is not None else 0,
            last_updated=row[18] if row[18] is not None else 0,
        )
