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

        # Verify that progress was loaded before collection (with default HK suffix)
        mock_tracker.load_progress.assert_called_once_with("ps5_games_HK")

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

        # Should clear progress first in full mode (with default HK suffix)
        mock_tracker.clear_progress.assert_called_once_with("ps5_games_HK")


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


class TestRegionSupport:
    """Test that Pipeline passes region through to collector and client."""

    @pytest.mark.asyncio
    async def test_run_full_passes_region_to_client(self, mock_settings, sample_collection_stats):
        """run_full_collection should pass region to _get_psstore_client."""
        pipeline = CollectionPipeline(mock_settings)

        mock_db = MagicMock()
        mock_tracker = MagicMock()
        mock_tracker.load_progress.return_value = None
        mock_collector = MagicMock()
        mock_collector.collect_category = AsyncMock(return_value=sample_collection_stats)

        pipeline._get_database = MagicMock(return_value=mock_db)
        pipeline._get_progress_tracker = MagicMock(return_value=mock_tracker)
        pipeline._get_psstore_client = MagicMock(return_value=MagicMock())
        pipeline._get_collector = MagicMock(return_value=mock_collector)

        await pipeline.run_full_collection("ps5_games", region="US")

        # Should pass region="US" to client factory
        pipeline._get_psstore_client.assert_called_once_with("US")

    @pytest.mark.asyncio
    async def test_run_full_passes_region_to_collector(self, mock_settings, sample_collection_stats):
        """run_full_collection should pass region to _get_collector."""
        pipeline = CollectionPipeline(mock_settings)

        mock_client = MagicMock()
        mock_db = MagicMock()
        mock_tracker = MagicMock()
        mock_tracker.load_progress.return_value = None
        mock_collector = MagicMock()
        mock_collector.collect_category = AsyncMock(return_value=sample_collection_stats)

        pipeline._get_database = MagicMock(return_value=mock_db)
        pipeline._get_progress_tracker = MagicMock(return_value=mock_tracker)
        pipeline._get_psstore_client = MagicMock(return_value=mock_client)
        pipeline._get_collector = MagicMock(return_value=mock_collector)

        await pipeline.run_full_collection("ps5_games", region="JP")

        # Verify collector was created with region
        call_kwargs = pipeline._get_collector.call_args
        assert call_kwargs.kwargs.get("region") == "JP"

    @pytest.mark.asyncio
    async def test_run_full_default_region_is_hk(self, mock_settings, sample_collection_stats):
        """Default region should be 'HK' for backward compatibility."""
        pipeline = CollectionPipeline(mock_settings)

        mock_db = MagicMock()
        mock_tracker = MagicMock()
        mock_tracker.load_progress.return_value = None
        mock_collector = MagicMock()
        mock_collector.collect_category = AsyncMock(return_value=sample_collection_stats)

        pipeline._get_database = MagicMock(return_value=mock_db)
        pipeline._get_progress_tracker = MagicMock(return_value=mock_tracker)
        pipeline._get_psstore_client = MagicMock(return_value=MagicMock())
        pipeline._get_collector = MagicMock(return_value=mock_collector)

        await pipeline.run_full_collection("ps5_games")

        # Default region should be HK
        pipeline._get_psstore_client.assert_called_once_with("HK")
        call_kwargs = pipeline._get_collector.call_args
        assert call_kwargs.kwargs.get("region") == "HK"

    @pytest.mark.asyncio
    async def test_progress_key_includes_region(self, mock_settings, sample_collection_stats):
        """Progress tracker key should include region suffix."""
        pipeline = CollectionPipeline(mock_settings)

        mock_db = MagicMock()
        mock_tracker = MagicMock()
        mock_tracker.load_progress.return_value = None
        mock_collector = MagicMock()
        mock_collector.collect_category = AsyncMock(return_value=sample_collection_stats)

        pipeline._get_database = MagicMock(return_value=mock_db)
        pipeline._get_progress_tracker = MagicMock(return_value=mock_tracker)
        pipeline._get_psstore_client = MagicMock(return_value=MagicMock())
        pipeline._get_collector = MagicMock(return_value=mock_collector)

        await pipeline.run_full_collection("ps5_games", region="TW")

        # Progress load/save should use region-prefixed key
        mock_tracker.load_progress.assert_called_once_with("ps5_games_TW")


class TestMultiRegionCollection:
    """Test multi-region collection orchestration."""

    @pytest.mark.asyncio
    async def test_collects_multiple_regions_sequentially(self, mock_settings):
        """run_multi_region_collection should loop over each region."""
        pipeline = CollectionPipeline(mock_settings)

        stats_hk = {"total_fetched": 10, "total_stored": 10, "total_images": 20, "errors": []}
        stats_us = {"total_fetched": 15, "total_stored": 15, "total_images": 30, "errors": []}

        original_run = AsyncMock(side_effect=[
            {**stats_hk, "category": "ps5_games", "success": True, "duration_seconds": 1.0},
            {**stats_us, "category": "ps5_games", "success": True, "duration_seconds": 1.5},
        ])

        with patch.object(pipeline, "run_full_collection", original_run):
            result = await pipeline.run_multi_region_collection(
                regions=["HK", "US"],
                category_key="ps5_games",
            )

        assert result["success"] is True
        assert result["regions_collected"] == 2
        assert result["total_stored"] == 25  # 10 + 15
        assert result["total_images"] == 50  # 20 + 30
        # Should have called run_full_collection twice
        assert original_run.call_count == 2

    @pytest.mark.asyncio
    async def test_multi_region_aggregates_errors(self, mock_settings):
        """Multi-region should aggregate errors from all regions."""
        pipeline = CollectionPipeline(mock_settings)

        stats_ok = {
            "total_fetched": 10, "total_stored": 10,
            "total_images": 20, "errors": [],
            "category": "ps5_games", "success": True, "duration_seconds": 1.0,
        }
        stats_err = {
            "total_fetched": 5, "total_stored": 3,
            "total_images": 6, "errors": ["timeout"],
            "category": "ps5_games", "success": False, "duration_seconds": 2.0,
        }

        original_run = AsyncMock(side_effect=[stats_ok, stats_err])

        with patch.object(pipeline, "run_full_collection", original_run):
            result = await pipeline.run_multi_region_collection(
                regions=["HK", "JP"],
                category_key="ps5_games",
            )

        assert result["success"] is False  # JP had error
        assert result["regions_collected"] == 2
        assert result["total_stored"] == 13  # 10 + 3
        assert len(result["per_region_results"]) == 2
        assert result["per_region_results"][1]["region"] == "JP"
        assert result["per_region_results"][1]["success"] is False

    @pytest.mark.asyncio
    async def test_multi_region_empty_list_returns_zero(self, mock_settings):
        """Empty regions list should return zero-collected result."""
        pipeline = CollectionPipeline(mock_settings)

        result = await pipeline.run_multi_region_collection(
            regions=[],
            category_key="ps5_games",
        )

        assert result["regions_collected"] == 0
        assert result["total_stored"] == 0
        assert result["success"] is False  # Empty regions = no work done
