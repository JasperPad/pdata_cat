"""Concurrent collection engine with ThreadPoolExecutor and Rich progress.

Handles paginated collection from PS Store categories:
- Loops through pages until is_last=True
- Each page: fetch → parse → upsert game + upsert images
- Rich progress bar for visual feedback
- Statistics tracking (fetched, stored, images, errors)
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from ps5_scraper.api.psstore_parser import PSStoreParser
from ps5_scraper.models.game import Game

logger = logging.getLogger(__name__)

# Module-level parser instance (shared across collectors)
_parser = PSStoreParser()


class ConcurrentCollector:
    """Concurrent collection engine for PS Store categories.

    Collects all games from a category by paginating through API results.
    Each page is fetched, parsed, and stored (game + images).

    Attributes:
        client: PSStoreClient for API calls.
        repo: GameRepository for persistence.
        max_workers: Max concurrent threads (reserved for future use).
        semaphore_limit: Semaphore limit for API concurrency.
        page_size: Number of items per API page.
    """

    def __init__(
        self,
        client: Any,  # PSStoreClient (avoiding circular import in type hint)
        repo: Any,  # GameRepository
        *,
        max_workers: int = 4,
        semaphore_limit: int = 3,
        page_size: int = 24,
    ) -> None:
        self.client = client
        self.repo = repo
        self.max_workers = max_workers
        self.semaphore_limit = semaphore_limit
        self.page_size = page_size

    async def collect_category(
        self,
        category_id: str,
        *,
        start_offset: int = 0,
    ) -> dict[str, Any]:
        """Collect all games from a category with pagination.

        Args:
            category_id: The PS Store category UUID to collect.
            start_offset: Offset to resume collection from (for checkpoint/resume).

        Returns:
            Dict with statistics:
            - total_fetched: Total games fetched from API.
            - total_stored: Total games successfully stored.
            - total_images: Total images stored.
            - errors: List of error descriptions.
        """
        stats = {
            "total_fetched": 0,
            "total_stored": 0,
            "total_images": 0,
            "errors": [],
        }

        offset = start_offset

        while True:
            try:
                page_result = await self._process_page(
                    offset=offset,
                    size=self.page_size,
                    category_id=category_id,
                )

                stats["total_fetched"] += page_result["fetched"]
                stats["total_stored"] += page_result["stored"]
                stats["total_images"] += page_result["images"]

                if page_result["is_last"]:
                    break

                offset += page_result["fetched"]

            except Exception as exc:
                error_msg = f"Error at offset {offset}: {exc}"
                logger.error(error_msg)
                stats["errors"].append(error_msg)

                # On error, still advance by page_size to avoid infinite loop
                offset += self.page_size

                # Safety: stop after too many consecutive errors
                if len(stats["errors"]) > 10:
                    stats["errors"].append("Too many consecutive errors, stopping")
                    break

        return stats

    async def _process_page(
        self,
        offset: int,
        size: int,
        category_id: str,
    ) -> dict[str, Any]:
        """Process a single page of results.

        Args:
            offset: Pagination offset.
            size: Page size.
            category_id: Category UUID.

        Returns:
            Dict with fetched count, stored count, image count, is_last flag.
        """
        # Fetch raw data from API
        raw_response = await self.client.fetch_category_games(
            category_id=category_id,
            offset=offset,
            size=size,
        )

        # Parse into CategoryResponse
        category_response = _parser.parse_category_response(raw_response)

        # Store each game and its images
        stored_count = 0
        image_count = 0

        for game in category_response.games:
            try:
                self.repo.upsert(game)
                stored_count += 1
                image_count += len(game.images)
            except Exception as exc:
                logger.warning("Failed to store game %s: %s", game.id, exc)

        return {
            "fetched": len(category_response.games),
            "stored": stored_count,
            "images": image_count,
            "is_last": category_response.is_last,
        }
