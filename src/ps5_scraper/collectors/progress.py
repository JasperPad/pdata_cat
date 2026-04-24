"""SQLite-based progress tracker for checkpoint/resume support.

Tracks collection progress per category using a SQLite table.
Supports save/load/clear/is_completed operations for
breakpoint-resume collection (断点续采).
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

# SQL for the progress tracking table
CREATE_PROGRESS_TABLE = """
CREATE TABLE IF NOT EXISTS collection_progress (
    category_id TEXT PRIMARY KEY,
    offset INTEGER NOT NULL DEFAULT 0,
    total_count INTEGER NOT NULL DEFAULT 0,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""


class ProgressTracker:
    """Track collection progress for checkpoint/resume support.

    Uses SQLite to persist progress so collection can resume from where it
    left off after interruption.

    Args:
        db: DatabaseManager instance for database access.
    """

    def __init__(self, db) -> None:  # DatabaseManager — avoid circular import
        self.db = db
        self._ensure_table()

    def _ensure_table(self) -> None:
        """Create the progress table if it doesn't exist."""
        with self.db.get_cursor() as cursor:
            cursor.execute(CREATE_PROGRESS_TABLE)

    def save_progress(
        self,
        category_id: str,
        offset: int,
        total_count: int,
    ) -> None:
        """Save current collection progress for a category.

        Args:
            category_id: The category key being collected.
            offset: Current pagination offset (next page to fetch).
            total_count: Total number of items in the category.
        """
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO collection_progress (category_id, offset, total_count)
                VALUES (?, ?, ?)
                ON CONFLICT(category_id) DO UPDATE SET
                    offset = excluded.offset,
                    total_count = excluded.total_count,
                    updated_at = CURRENT_TIMESTAMP
            """, (category_id, offset, total_count))

        logger.debug(
            "Progress saved: category=%s, offset=%d, total=%d",
            category_id, offset, total_count,
        )

    def load_progress(self, category_id: str) -> dict | None:
        """Load saved progress for a category.

        Args:
            category_id: The category key to look up.

        Returns:
            Dict with 'offset' and 'total_count', or None if no progress found.
        """
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT offset, total_count FROM collection_progress WHERE category_id = ?",
                (category_id,),
            )
            row = cursor.fetchone()

        if row is None:
            return None

        return {
            "offset": row[0],
            "total_count": row[1],
        }

    def clear_progress(self, category_id: str) -> None:
        """Clear saved progress for a category (for full re-collection).

        Args:
            category_id: The category key to clear.
        """
        with self.db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "DELETE FROM collection_progress WHERE category_id = ?",
                (category_id,),
            )

        logger.debug("Progress cleared for category: %s", category_id)

    def is_completed(self, category_id: str) -> bool:
        """Check if collection for a category is complete.

        A category is considered complete when the saved offset >= total_count.

        Args:
            category_id: The category key to check.

        Returns:
            True if completed (or no progress exists), False otherwise.
        """
        progress = self.load_progress(category_id)
        if progress is None:
            return False

        return progress["offset"] >= progress["total_count"]
