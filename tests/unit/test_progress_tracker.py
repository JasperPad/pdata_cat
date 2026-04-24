"""Tests for ProgressTracker: SQLite-based checkpoint/resume support."""

import pytest

from ps5_scraper.collectors.progress import ProgressTracker
from ps5_scraper.storage.database import DatabaseManager


@pytest.fixture
def db_manager(tmp_path):
    """Create a DatabaseManager with a temp database."""
    db = DatabaseManager(db_path=str(tmp_path / "progress_test.db"))
    db.initialize()
    return db


@pytest.fixture
def tracker(db_manager):
    """Create a ProgressTracker with initialized DB."""
    return ProgressTracker(db_manager)


class TestSaveAndLoad:
    """Test save_progress and load_progress round-trip."""

    def test_save_and_load_roundtrip(self, tracker):
        """Saving progress then loading should return the same values."""
        tracker.save_progress("cat-ps5", offset=48, total_count=200)

        result = tracker.load_progress("cat-ps5")
        assert result is not None
        assert result["offset"] == 48
        assert result["total_count"] == 200

    def test_save_overwrites_previous(self, tracker):
        """Second save should overwrite the first."""
        tracker.save_progress("cat-ps5", offset=24, total_count=100)
        tracker.save_progress("cat-ps5", offset=72, total_count=200)

        result = tracker.load_progress("cat-ps5")
        assert result["offset"] == 72
        assert result["total_count"] == 200

    def test_save_zero_offset(self, tracker):
        """Should handle zero offset (beginning of collection)."""
        tracker.save_progress("cat-new", offset=0, total_count=150)

        result = tracker.load_progress("cat-new")
        assert result is not None
        assert result["offset"] == 0
        assert result["total_count"] == 150


class TestLoadNonexistent:
    """Test loading progress for categories that don't exist."""

    def test_load_nonexistent_returns_none(self, tracker):
        """Loading a category that was never saved returns None."""
        result = tracker.load_progress("nonexistent-cat")
        assert result is None

    def test_load_after_clear_returns_none(self, tracker):
        """Loading after clear_progress returns None."""
        tracker.save_progress("cat-temp", offset=50, total_count=100)
        tracker.clear_progress("cat-temp")

        result = tracker.load_progress("cat-temp")
        assert result is None


class TestClearProgress:
    """Test clearing saved progress."""

    def test_clear_removes_progress(self, tracker):
        """clear_progress should remove the saved entry."""
        tracker.save_progress("cat-clear", offset=30, total_count=90)
        
        # Verify it exists before clearing
        assert tracker.load_progress("cat-clear") is not None
        
        # Clear it
        tracker.clear_progress("cat-clear")
        
        # Verify it's gone
        assert tracker.load_progress("cat-clear") is None

    def test_clear_nonexistent_no_error(self, tracker):
        """Clearing a non-existent category should not raise."""
        tracker.clear_progress("never-saved")  # Should not raise


class TestIsCompleted:
    """Test the is_completed method."""

    def test_not_completed_when_offset_less_than_total(self, tracker):
        """Should return False when offset < total_count (more to collect)."""
        tracker.save_progress("cat-partial", offset=48, total_count=200)
        assert tracker.is_completed("cat-partial") is False

    def test_completed_when_offset_equals_total(self, tracker):
        """Should return True when offset >= total_count."""
        tracker.save_progress("cat-done", offset=200, total_count=200)
        assert tracker.is_completed("cat-done") is True

    def test_completed_when_offset_exceeds_total(self, tracker):
        """Should return True when offset > total_count (edge case)."""
        tracker.save_progress("cat-over", offset=210, total_count=200)
        assert tracker.is_completed("cat-over") is True

    def test_not_completed_for_nonexistent(self, tracker):
        """Non-existent category should return False (not completed)."""
        assert tracker.is_completed("nonexistent") is False

    def test_not_completed_after_partial_save(self, tracker):
        """Partially collected category is not complete."""
        tracker.save_progress("cat-half", offset=100, total_count=200)
        assert tracker.is_completed("cat-half") is False


class TestMultipleCategories:
    """Test tracking progress for multiple independent categories."""

    def test_independent_category_tracking(self, tracker):
        """Each category's progress should be independent."""
        tracker.save_progress("ps5_games", offset=96, total_count=500)
        tracker.save_progress("deals", offset=24, total_count=100)
        tracker.save_progress("free_games", offset=12, total_count=50)

        ps5_result = tracker.load_progress("ps5_games")
        deals_result = tracker.load_progress("deals")
        free_result = tracker.load_progress("free_games")

        assert ps5_result["offset"] == 96
        assert deals_result["offset"] == 24
        assert free_result["offset"] == 12

    def test_clear_one_doesnt_affect_others(self, tracker):
        """Clearing one category shouldn't affect others."""
        tracker.save_progress("cat-a", offset=10, total_count=100)
        tracker.save_progress("cat-b", offset=20, total_count=200)

        tracker.clear_progress("cat-a")

        assert tracker.load_progress("cat-a") is None
        assert tracker.load_progress("cat-b") is not None
        assert tracker.load_progress("cat-b")["offset"] == 20


class TestTableInitialization:
    """Test that the progress table is created on demand."""

    def test_table_created_on_first_save(self, db_manager):
        """First save should create the progress table automatically."""
        tracker = ProgressTracker(db_manager)
        tracker.save_progress("init-test", offset=0, total_count=10)

        result = tracker.load_progress("init-test")
        assert result is not None

    def test_multiple_trackers_share_db(self, db_manager):
        """Multiple ProgressTracker instances on same DB should share data."""
        tracker1 = ProgressTracker(db_manager)
        tracker2 = ProgressTracker(db_manager)

        tracker1.save_progress("shared-cat", offset=42, total_count=100)
        result = tracker2.load_progress("shared-cat")

        assert result is not None
        assert result["offset"] == 42
