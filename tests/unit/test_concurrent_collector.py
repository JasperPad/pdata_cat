"""Tests for ConcurrentCollector: multi-region collection engine."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from ps5_scraper.api.psstore_parser import PSStoreParser
from ps5_scraper.collectors.concurrent import ConcurrentCollector


# ─── Fixtures ──────────────────────────────────────────────────────

@pytest.fixture
def mock_client():
    """Mock PSStoreClient."""
    client = AsyncMock()
    client.fetch_category_games = AsyncMock(return_value={
        "data": {
            "categoryGridRetrieve": {
                "pageInfo": {"totalCount": 2, "offset": 0, "size": 24, "isLast": True},
                "products": [
                    {
                        "id": "GAME-001",
                        "name": "Test Game 1",
                        "platforms": ["PS5"],
                        "localizedStoreDisplayClassification": "Game",
                        "releaseDate": "2024-01-01",
                        "providerName": "TestDev",
                        "topGenre": "Action",
                        "ageRatingLabel": "12+",
                        "starRating": {"score": 4.0, "total": 100},
                        "price": None,
                        "media": [
                            {"role": "MASTER", "type": "IMAGE", "url": "https://img1.jpg", "width": 1920, "height": 1080},
                        ],
                        "skus": [{"id": "sku-1"}],
                    },
                    {
                        "id": "GAME-002",
                        "name": "Test Game 2",
                        "platforms": ["PS5"],
                        "localizedStoreDisplayClassification": "Game",
                        "price": None,
                        "media": [],
                        "skus": [],
                    },
                ],
            }
        }
    })
    return client


@pytest.fixture
def mock_repo():
    """Mock GameRepository."""
    repo = MagicMock()
    repo.upsert = MagicMock()
    return repo


class TestRegionPassThrough:
    """Test that region is passed through to parsed games."""

    @pytest.mark.asyncio
    async def test_default_region_hk(self, mock_client, mock_repo):
        """Default collector should use HK region."""
        collector = ConcurrentCollector(mock_client, mock_repo)
        stats = await collector.collect_category("test-category-id")

        assert stats["total_stored"] == 2
        # Verify stored games have region=HK
        for call in mock_repo.upsert.call_args_list:
            game = call[0][0]  # First positional arg is Game
            assert game.region == "HK"

    @pytest.mark.asyncio
    async def test_us_region(self, mock_client, mock_repo):
        """Collector with region=US should store games with US."""
        collector = ConcurrentCollector(mock_client, mock_repo, region="US")
        stats = await collector.collect_category("test-category-id")

        assert stats["total_stored"] == 2
        for call in mock_repo.upsert.call_args_list:
            game = call[0][0]
            assert game.region == "US"

    @pytest.mark.asyncio
    async def test_jp_region(self, mock_client, mock_repo):
        """Collector with region=JP should store games with JP."""
        collector = ConcurrentCollector(mock_client, mock_repo, region="JP")
        stats = await collector.collect_category("test-category-id")

        assert stats["total_stored"] == 2
        for call in mock_repo.upsert.call_args_list:
            game = call[0][0]
            assert game.region == "JP"

    @pytest.mark.asyncio
    async def test_tw_region(self, mock_client, mock_repo):
        """Collector with region=TW should store games with TW."""
        collector = ConcurrentCollector(mock_client, mock_repo, region="TW")
        stats = await collector.collect_category("test-category-id")

        assert stats["total_stored"] == 2
        for call in mock_repo.upsert.call_args_list:
            game = call[0][0]
            assert game.region == "TW"


class TestStatistics:
    """Test collection statistics are accurate."""

    @pytest.mark.asyncio
    async def test_stats_count_fetched_and_stored(self, mock_client, mock_repo):
        """Stats should correctly count fetched and stored games."""
        collector = ConcurrentCollector(mock_client, mock_repo, region="US")
        stats = await collector.collect_category("test-cat")

        assert stats["total_fetched"] == 2
        assert stats["total_stored"] == 2
        assert stats["total_images"] == 1  # Only GAME-001 has an image
        assert len(stats["errors"]) == 0

    @pytest.mark.asyncio
    async def test_stats_with_errors(self, mock_client, mock_repo):
        """Errors during storage should be tracked as warnings but not stop collection."""
        # Storage errors are logged as warnings (not added to stats errors)
        # This verifies the collector continues even when individual games fail
        mock_repo.upsert.side_effect = Exception("DB error")
        collector = ConcurrentCollector(mock_client, mock_repo)
        stats = await collector.collect_category("test-cat")

        assert stats["total_fetched"] == 2
        assert stats["total_stored"] == 0  # All upserts failed
        # Storage errors don't go into stats["errors"]; they're logged as warnings
