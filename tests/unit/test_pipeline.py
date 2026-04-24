"""Tests for CollectionPipeline: orchestration layer with resume + stats."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ps5_scraper.collectors.pipelines import CollectionPipeline
from ps5_scraper.config import Settings


@pytest.fixture
def mock_settings():
    """Create a minimal Settings instance with temp DB path."""
    # Use a settings that won't try to load a real config file
    with patch.object(Settings, '_load_yaml', return_value={}):
        settings = Settings(config_file="/nonexistent.yaml")
        settings.db_path = ":memory:"
        return settings


@pytest.fixture
def sample_collection_stats():
    """Return typical collection statistics."""
    return {
        "total_fetched": 48,
        "total_stored": 48,
        "total_images": 120,
        "errors": [],
    }


class TestRunFullCollection:
    """Test the full collection pipeline execution."""

    @pytest.mark.asyncio
    async def test_calls_correct_subprocesses(self, mock_settings, sample_collection_stats):
        """run_full_collection should call load progress → collect → save → report."""
        pipeline = CollectionPipeline(mock_settings)

        # Mock all dependencies
        mock_db = MagicMock()
        mock_tracker = MagicMock()
        mock_collector = MagicMock()
        mock_collector.collect_category = AsyncMock(return_value=sample_collection_stats)

        pipeline._get_database = MagicMock(return_value=mock_db)
        pipeline._get_progress_tracker = MagicMock(return_value=mock_tracker)
        pipeline._get_psstore_client = MagicMock(return_value=MagicMock())
        pipeline._get_collector = MagicMock(return_value=mock_collector)

        result = await pipeline.run_full_collection("ps5_games")

        # Should have created database and tracker
        pipeline._get_database.assert_called_once()
        pipeline._get_progress_tracker.assert_called_once()
        pipeline._get_collector.assert_called_once()

        # Should have called collect on the collector
        mock_collector.collect_category.assert_called_once()

        # Result should contain stats
        assert result["total_fetched"] == 48
        assert result["total_stored"] == 48

    @pytest.mark.asyncio
    async def test_resumes_from_saved_offset(self, mock_settings, sample_collection_stats):
        """Pipeline should resume from saved offset if progress exists."""
        pipeline = CollectionPipeline(mock_settings)

        mock_tracker = MagicMock()
        mock_tracker.load_progress.return_value = {"offset": 48, "total_count": 200}

        mock_collector = MagicMock()
        mock_collector.collect_category = AsyncMock(return_value=sample_collection_stats)
        mock_db = MagicMock()

        pipeline._get_database = MagicMock(return_value=mock_db)
        pipeline._get_progress_tracker = MagicMock(return_value=mock_tracker)
        pipeline._get_psstore_client = MagicMock(return_value=MagicMock())
        pipeline._get_collector = MagicMock(return_value=mock_collector)

        await pipeline.run_full_collection("ps5_games")

        # Verify that progress was loaded before collection
        mock_tracker.load_progress.assert_called_once_with("ps5_games")

    @pytest.mark.asyncio
    async def test_full_mode_clears_progress_first(self, mock_settings, sample_collection_stats):
        """--full mode should clear progress before starting."""
        pipeline = CollectionPipeline(mock_settings)

        mock_tracker = MagicMock()
        mock_collector = MagicMock()
        mock_collector.collect_category = AsyncMock(return_value=sample_collection_stats)
        mock_db = MagicMock()

        pipeline._get_database = MagicMock(return_value=mock_db)
        pipeline._get_progress_tracker = MagicMock(return_value=mock_tracker)
        pipeline._get_psstore_client = MagicMock(return_value=MagicMock())
        pipeline._get_collector = MagicMock(return_value=mock_collector)

        await pipeline.run_full_collection("ps5_games", full_mode=True)

        # Should clear progress first in full mode
        mock_tracker.clear_progress.assert_called_once_with("ps5_games")


class TestStatisticsReport:
    """Test that the pipeline produces correct statistical reports."""

    @pytest.mark.asyncio
    async def test_report_includes_key_metrics(self, mock_settings):
        """Result should include fetched/stored/images/errors/category info."""
        pipeline = CollectionPipeline(mock_settings)

        stats = {
            "total_fetched": 100,
            "total_stored": 98,
            "total_images": 250,
            "errors": ["Error at offset 48: timeout"],
        }

        mock_tracker = MagicMock()
        mock_tracker.load_progress.return_value = None
        mock_collector = MagicMock()
        mock_collector.collect_category = AsyncMock(return_value=stats)
        mock_db = MagicMock()

        pipeline._get_database = MagicMock(return_value=mock_db)
        pipeline._get_progress_tracker = MagicMock(return_value=mock_tracker)
        pipeline._get_psstore_client = MagicMock(return_value=MagicMock())
        pipeline._get_collector = MagicMock(return_value=mock_collector)

        result = await pipeline.run_full_collection("deals")

        assert result["category"] == "deals"
        assert result["total_fetched"] == 100
        assert result["total_stored"] == 98
        assert result["total_images"] == 250
        assert len(result["errors"]) == 1
        assert "success" in result

    @pytest.mark.asyncio
    async def test_success_flag_true_when_no_errors(self, mock_settings):
        """success flag should be True when no errors occurred."""
        pipeline = CollectionPipeline(mock_settings)

        stats = {"total_fetched": 10, "total_stored": 10, "total_images": 20, "errors": []}

        mock_tracker = MagicMock()
        mock_tracker.load_progress.return_value = None
        mock_collector = MagicMock()
        mock_collector.collect_category = AsyncMock(return_value=stats)
        mock_db = MagicMock()

        pipeline._get_database = MagicMock(return_value=mock_db)
        pipeline._get_progress_tracker = MagicMock(return_value=mock_tracker)
        pipeline._get_psstore_client = MagicMock(return_value=MagicMock())
        pipeline._get_collector = MagicMock(return_value=mock_collector)

        result = await pipeline.run_full_collection("ps5_games")
        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_success_flag_false_when_errors(self, mock_settings):
        """success flag should be False when errors occurred."""
        pipeline = CollectionPipeline(mock_settings)

        stats = {
            "total_fetched": 10,
            "total_stored": 8,
            "total_images": 16,
            "errors": ["error 1", "error 2"],
        }

        mock_tracker = MagicMock()
        mock_tracker.load_progress.return_value = None
        mock_collector = MagicMock()
        mock_collector.collect_category = AsyncMock(return_value=stats)
        mock_db = MagicMock()

        pipeline._get_database = MagicMock(return_value=mock_db)
        pipeline._get_progress_tracker = MagicMock(return_value=mock_tracker)
        pipeline._get_psstore_client = MagicMock(return_value=MagicMock())
        pipeline._get_collector = MagicMock(return_value=mock_collector)

        result = await pipeline.run_full_collection("ps5_games")
        assert result["success"] is False


class TestPartialResultsOnError:
    """Test that partial results are returned even on errors."""

    @pytest.mark.asyncio
    async def test_partial_results_on_exception(self, mock_settings):
        """If collect raises exception, should still return partial results."""
        pipeline = CollectionPipeline(mock_settings)

        mock_tracker = MagicMock()
        mock_tracker.load_progress.return_value = None
        mock_collector = MagicMock()
        mock_collector.collect_category = AsyncMock(
            side_effect=Exception("Connection refused")
        )
        mock_db = MagicMock()

        pipeline._get_database = MagicMock(return_value=mock_db)
        pipeline._get_progress_tracker = MagicMock(return_value=mock_tracker)
        pipeline._get_psstore_client = MagicMock(return_value=MagicMock())
        pipeline._get_collector = MagicMock(return_value=mock_collector)

        result = await pipeline.run_full_collection("ps5_games")

        # Should not crash — returns error result
        assert result["success"] is False
        assert len(result["errors"]) >= 1


class TestGetStatus:
    """Test get_status method."""

    def test_status_returns_current_state(self, mock_settings):
        """get_status should return current pipeline status info."""
        pipeline = CollectionPipeline(mock_settings)

        mock_tracker = MagicMock()
        mock_tracker.load_progress.return_value = {
            "offset": 72,
            "total_count": 200,
        }

        pipeline._get_progress_tracker = MagicMock(return_value=mock_tracker)

        status = pipeline.get_status("ps5_games")

        assert status["category"] == "ps5_games"
        assert status["offset"] == 72
        assert status["total_count"] == 200
        assert status["is_completed"] is False  # 72 < 200

    def test_status_completed(self, mock_settings):
        """get_status should show completed when done."""
        pipeline = CollectionPipeline(mock_settings)

        mock_tracker = MagicMock()
        mock_tracker.load_progress.return_value = {
            "offset": 200,
            "total_count": 200,
        }

        pipeline._get_progress_tracker = MagicMock(return_value=mock_tracker)

        status = pipeline.get_status("ps5_games")
        assert status["is_completed"] is True

    def test_status_no_progress(self, mock_settings):
        """get_status should handle category with no saved progress."""
        pipeline = CollectionPipeline(mock_settings)

        mock_tracker = MagicMock()
        mock_tracker.load_progress.return_value = None

        pipeline._get_progress_tracker = MagicMock(return_value=mock_tracker)

        status = pipeline.get_status("new_category")
        assert status["has_progress"] is False
