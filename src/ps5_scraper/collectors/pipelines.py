"""Collection pipeline orchestration layer.

Coordinates the full collection workflow:
1. Load progress (checkpoint/resume)
2. Create ConcurrentCollector
3. Execute collection
4. Save progress
5. Output statistics report
"""

from __future__ import annotations

import logging
import time
from typing import Any

from ps5_scraper.api.psstore_client import PSStoreClient
from ps5_scraper.collectors.concurrent import ConcurrentCollector
from ps5_scraper.collectors.progress import ProgressTracker
from ps5_scraper.config import Settings
from ps5_scraper.storage.database import DatabaseManager
from ps5_scraper.storage.repositories import GameRepository

logger = logging.getLogger(__name__)


class CollectionPipeline:
    """Orchestrates the full data collection workflow.

    Manages the complete lifecycle: database setup, progress tracking,
    concurrent collection, and statistical reporting.

    Args:
        config: Settings instance with all configuration.
    """

    def __init__(self, config: Settings) -> None:
        self.config = config

    async def run_full_collection(
        self,
        category_key: str = "ps5_games",
        *,
        full_mode: bool = False,
    ) -> dict[str, Any]:
        """Run full collection for a category with checkpoint/resume support.

        Workflow:
        1. Initialize database and progress tracker
        2. If full_mode, clear existing progress (start fresh)
        3. Load saved offset for resume support
        4. Create ConcurrentCollector and execute collection
        5. Save updated progress
        6. Return statistics report

        Args:
            category_key: Category key from settings.category_ids.
            full_mode: If True, ignore saved progress and do full re-collection.

        Returns:
            Dict with:
            - category: The category key collected.
            - total_fetched/stored/images/errors: Collection stats.
            - success: True if no errors occurred.
            - duration_seconds: How long the collection took.
        """
        start_time = time.monotonic()

        # Get category ID from settings
        category_id = self.config.category_ids.get(category_key)
        if not category_id:
            return {
                "category": category_key,
                "success": False,
                "total_fetched": 0,
                "total_stored": 0,
                "total_images": 0,
                "errors": [f"Unknown category key: {category_key}"],
                "duration_seconds": 0.0,
            }

        # Set up infrastructure
        db = self._get_database()
        db.initialize()

        repo = GameRepository(db)
        tracker = self._get_progress_tracker(db)
        client = self._get_psstore_client()
        collector = self._get_collector(client, repo)

        # Handle full mode: clear progress first
        if full_mode:
            logger.info("Full mode: clearing progress for %s", category_key)
            tracker.clear_progress(category_key)

        # Load saved progress for resume
        saved_progress = tracker.load_progress(category_key)
        start_offset = 0
        if saved_progress and not full_mode:
            start_offset = saved_progress["offset"]
            logger.info(
                "Resuming %s from offset %d / %d",
                category_key, start_offset, saved_progress["total_count"],
            )

        # Execute collection
        try:
            stats = await collector.collect_category(category_id)
        except Exception as exc:
            error_msg = f"Collection failed: {exc}"
            logger.error(error_msg)
            return {
                "category": category_key,
                "success": False,
                "total_fetched": 0,
                "total_stored": 0,
                "total_images": 0,
                "errors": [error_msg],
                "duration_seconds": time.monotonic() - start_time,
            }

        # Save progress after successful collection
        # Use fetched count as new offset (we've processed up to this point)
        final_offset = start_offset + stats["total_fetched"]
        tracker.save_progress(
            category_id=category_key,
            offset=final_offset,
            total_count=stats.get("total_count", final_offset) or final_offset,
        )

        duration = time.monotonic() - start_time
        success = len(stats["errors"]) == 0

        result = {
            "category": category_key,
            "success": success,
            **stats,
            "duration_seconds": round(duration, 2),
        }

        logger.info(
            "Collection complete: %d games, %d images, %.1fs, errors=%d",
            result["total_stored"],
            result["total_images"],
            duration,
            len(result["errors"]),
        )

        return result

    def get_status(self, category_key: str = "ps5_games") -> dict[str, Any]:
        """Get current status summary for a category.

        Args:
            category_key: Category key to check.

        Returns:
            Dict with category info and progress state.
        """
        db = self._get_database()
        db.initialize()
        tracker = self._get_progress_tracker(db)

        progress = tracker.load_progress(category_key)

        if progress is None:
            return {
                "category": category_key,
                "has_progress": False,
                "offset": 0,
                "total_count": 0,
                "is_completed": False,
            }

        is_done = progress["offset"] >= progress["total_count"]

        return {
            "category": category_key,
            "has_progress": True,
            "offset": progress["offset"],
            "total_count": progress["total_count"],
            "is_completed": is_done,
        }

    async def run_incremental(self, category_key: str = "ps5_games") -> dict[str, Any]:
        """Incremental update mode (reserved for future versions).

        Future implementation will compare timestamps and only update changed records.

        Args:
            category_key: Category key to incrementally update.

        Returns:
            Placeholder result dict.
        """
        logger.info("Incremental mode not yet implemented, falling back to full collection")
        return await self.run_full_collection(category_key)

    # ─── Factory helpers (overridable for testing) ────────────────

    def _get_database(self) -> DatabaseManager:
        """Create a DatabaseManager from settings."""
        return self.config.get_database()

    def _get_progress_tracker(self, db: DatabaseManager) -> ProgressTracker:
        """Create a ProgressTracker."""
        return ProgressTracker(db)

    def _get_psstore_client(self) -> PSStoreClient:
        """Create a PSStoreClient from settings."""
        return self.config.get_psstore_client()

    def _get_collector(
        self,
        client: PSStoreClient,
        repo: Any,  # GameRepository
    ) -> ConcurrentCollector:
        """Create a ConcurrentCollector."""
        return ConcurrentCollector(
            client=client,
            repo=repo,
            max_workers=self.config.max_workers,
            semaphore_limit=self.config.semaphore_limit,
            page_size=self.config.page_size,
        )
