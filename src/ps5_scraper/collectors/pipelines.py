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
        region: str = "HK",
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
            region: PS Store region code (e.g., 'HK', 'US', 'JP'). Defaults to 'HK'.

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

        # Progress key includes region to allow independent tracking per region
        progress_key = f"{category_key}_{region}"

        client = self._get_psstore_client(region)
        collector = self._get_collector(client, repo, region=region)

        # Handle full mode: clear progress first
        if full_mode:
            logger.info("Full mode: clearing progress for %s", progress_key)
            tracker.clear_progress(progress_key)

        # Load saved progress for resume
        saved_progress = tracker.load_progress(progress_key)
        start_offset = 0
        if saved_progress and not full_mode:
            start_offset = saved_progress["offset"]
            logger.info(
                "Resuming %s from offset %d / %d",
                progress_key, start_offset, saved_progress["total_count"],
            )

        # Execute collection
        try:
            stats = await collector.collect_category(category_id, start_offset=start_offset)
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
            category_id=progress_key,
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

    def _get_psstore_client(self, region: str = "HK") -> PSStoreClient:
        """Create a PSStoreClient from settings.

        Args:
            region: PS Store region code for locale/currency configuration.
        """
        return self.config.get_psstore_client(region)

    def _get_collector(
        self,
        client: PSStoreClient,
        repo: Any,  # GameRepository
        *,
        region: str = "HK",
    ) -> ConcurrentCollector:
        """Create a ConcurrentCollector.

        Args:
            client: Configured PS Store API client.
            repo: Game repository for storage.
            region: Region code to pass through to parser/collector.
        """
        return ConcurrentCollector(
            client=client,
            repo=repo,
            max_workers=self.config.max_workers,
            semaphore_limit=self.config.semaphore_limit,
            page_size=self.config.page_size,
            region=region,
        )

    async def run_multi_region_collection(
        self,
        regions: list[str],
        category_key: str = "ps5_games",
        *,
        full_mode: bool = False,
    ) -> dict[str, Any]:
        """Run collection across multiple PS Store regions sequentially.

        For each region in the list, calls run_full_collection with that region.
        Aggregates results from all regions into a combined report.

        Args:
            regions: List of region codes (e.g., ['HK', 'US', 'JP']).
            category_key: Category key from settings.category_ids.
            full_mode: If True, clear progress and re-collect all regions.

        Returns:
            Dict with:
            - regions_collected: Number of regions processed.
            - total_fetched/stored/images/errors: Aggregated stats.
            - per_region_results: List of per-region result dicts (with 'region' field).
            - success: True if ALL regions succeeded without errors.
            - duration_seconds: Total wall-clock time.
        """
        start_time = time.monotonic()

        # Guard: empty regions list
        if not regions:
            logger.warning("run_multi_region_collection called with empty regions list")
            return {
                "category": category_key,
                "regions_collected": 0,
                "total_fetched": 0,
                "total_stored": 0,
                "total_images": 0,
                "errors": ["Empty regions list provided"],
                "per_region_results": [],
                "success": False,
                "duration_seconds": 0.0,
            }

        per_region_results: list[dict[str, Any]] = []
        aggregated = {
            "total_fetched": 0,
            "total_stored": 0,
            "total_images": 0,
            "errors": [],
        }

        logger.info("Starting multi-region collection for %d regions: %s", len(regions), regions)

        for region_code in regions:
            logger.info("Collecting region %s...", region_code)
            region_result = await self.run_full_collection(
                category_key,
                full_mode=full_mode,
                region=region_code,
            )
            region_result["region"] = region_code
            per_region_results.append(region_result)

            # Aggregate stats
            aggregated["total_fetched"] += region_result.get("total_fetched", 0)
            aggregated["total_stored"] += region_result.get("total_stored", 0)
            aggregated["total_images"] += region_result.get("total_images", 0)
            if region_result.get("errors"):
                aggregated["errors"].extend(region_result["errors"])

        duration = time.monotonic() - start_time
        all_success = all(r.get("success", False) for r in per_region_results)

        result = {
            "category": category_key,
            "regions_collected": len(regions),
            **aggregated,
            "per_region_results": per_region_results,
            "success": all_success and len(regions) > 0,
            "duration_seconds": round(duration, 2),
        }

        logger.info(
            "Multi-region collection complete: %d regions, %d games, %d images, %.1fs",
            len(regions),
            result["total_stored"],
            result["total_images"],
            duration,
        )

        return result
