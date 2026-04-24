"""Tests for ConcurrentCollector: paginated collection with progress and stats."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ps5_scraper.api.psstore_parser import PSStoreParser
from ps5_scraper.collectors.concurrent import ConcurrentCollector
from ps5_scraper.models.game import Game, GameImage


@pytest.fixture
def mock_client():
    """Create a mock PSStoreClient."""
    client = MagicMock()
    client.fetch_category_games = AsyncMock()
    return client


@pytest.fixture
def mock_repo():
    """Create a mock GameRepository."""
    repo = MagicMock()
    repo.upsert = MagicMock()
    repo.upsert_images = MagicMock()
    return repo


@pytest.fixture
def parser():
    """Return a real parser instance for use in tests."""
    return PSStoreParser()


@pytest.fixture
def sample_raw_response_single_page(parser):
    """Raw API response for a single (last) page with 2 games."""
    return {
        "data": {
            "categoryGridRetrieve": {
                "pageInfo": {
                    "totalCount": 2,
                    "offset": 0,
                    "size": 2,
                    "isLast": True,
                },
                "products": [
                    {
                        "id": "game-001",
                        "name": "Test Game 1",
                        "platforms": ["PS5"],
                        "localizedStoreDisplayClassification": "Full Game",
                        "releaseDate": "2024-01-15",
                        "providerName": "Test Publisher",
                        "topGenre": "Action",
                        "ageRatingLabel": "16+",
                        "starRating": {"score": 4.5, "total": 1000},
                        "price": {
                            "basePrice": "HK$468.00",
                            "discountedPrice": "",
                            "discountText": "",
                            "isFree": False,
                            "isExclusive": False,
                            "serviceBranding": ["NONE"],
                            "upsellText": "",
                        },
                        "media": [
                            {"role": "MASTER", "type": "IMAGE", "url": "https://img.game1.master.jpg", "width": 1280, "height": 720},
                            {"role": "SCREENSHOT", "type": "IMAGE", "url": "https://img.game1.ss.jpg"},
                        ],
                        "skus": [{"id": "sku-001"}],
                    },
                    {
                        "id": "game-002",
                        "name": "Test Game 2",
                        "platforms": ["PS5"],
                        "localizedStoreDisplayClassification": "Full Game",
                        "releaseDate": "2024-02-20",
                        "providerName": "Test Dev",
                        "topGenre": "RPG",
                        "ageRatingLabel": "12+",
                        "starRating": {"score": 3.8, "total": 500},
                        "price": None,
                        "media": [
                            {"role": "MASTER", "type": "IMAGE", "url": "https://img.game2.master.jpg"},
                        ],
                        "skus": [],
                    },
                ],
            }
        }
    }


@pytest.fixture
def sample_raw_response_page1(sample_raw_response_single_page):
    """First page of multi-page response (not last)."""
    data = dict(sample_raw_response_single_page)
    data["data"]["categoryGridRetrieve"]["pageInfo"]["isLast"] = False
    data["data"]["categoryGridRetrieve"]["pageInfo"]["totalCount"] = 3
    return data


@pytest.fixture
def sample_raw_response_page2_last(parser):
    """Second (last) page of multi-page response with 1 game."""
    return {
        "data": {
            "categoryGridRetrieve": {
                "pageInfo": {
                    "totalCount": 3,
                    "offset": 2,
                    "size": 1,
                    "isLast": True,
                },
                "products": [
                    {
                        "id": "game-003",
                        "name": "Test Game 3",
                        "platforms": ["PS5"],
                        "localizedStoreDisplayClassification": "Full Game",
                        "releaseDate": "2024-03-10",
                        "providerName": "Test Studio",
                        "topGenre": "Adventure",
                        "ageRatingLabel": "18+",
                        "starRating": {"score": 4.9, "total": 2000},
                        "price": {
                            "basePrice": "HK$0.00",
                            "discountedPrice": "",
                            "discountText": "",
                            "isFree": True,
                            "isExclusive": False,
                            "serviceBranding": [],
                            "upsellText": "",
                        },
                        "media": [],
                        "skus": [{"id": "sku-003"}],
                    },
                ],
            }
        }
    }


class TestSinglePageCollection:
    """Test collecting a single-page category."""

    @pytest.mark.asyncio
    async def test_single_page_collect(self, mock_client, mock_repo, sample_raw_response_single_page):
        """Should fetch one page, parse it, upsert games and images."""
        mock_client.fetch_category_games.return_value = sample_raw_response_single_page

        collector = ConcurrentCollector(client=mock_client, repo=mock_repo)
        result = await collector.collect_category("cat-001")

        # Should have called API once
        assert mock_client.fetch_category_games.call_count == 1
        mock_client.fetch_category_games.assert_called_once_with(
            category_id="cat-001", offset=0, size=24
        )

        # Should have upserted 2 games
        assert mock_repo.upsert.call_count == 2

        # Stats should reflect the results
        assert result["total_fetched"] == 2
        assert result["total_stored"] == 2
        assert result["total_images"] > 0  # game-001 has 2 images, game-002 has 1
        assert result["errors"] == []

    @pytest.mark.asyncio
    async def test_upsert_receives_game_objects(self, mock_client, mock_repo, sample_raw_response_single_page):
        """upsert should be called with Game model instances."""
        mock_client.fetch_category_games.return_value = sample_raw_response_single_page

        collector = ConcurrentCollector(client=mock_client, repo=mock_repo)
        await collector.collect_category("cat-001")

        for call in mock_repo.upsert.call_args_list:
            game_arg = call[0][0]
            assert isinstance(game_arg, Game)
            assert isinstance(game_arg.id, str)
            assert isinstance(game_arg.name, str)


class TestMultiPageCollection:
    """Test automatic pagination through multiple pages."""

    @pytest.mark.asyncio
    async def test_multi_page_auto_pagination(self, mock_client, mock_repo, sample_raw_response_page1, sample_raw_response_page2_last):
        """Should automatically paginate until is_last=True."""
        # Page 1: not last → triggers page 2
        # Page 2: is_last=True → stop
        call_count = 0
        original_call = mock_client.fetch_category_games

        async def side_effect(*args, **kwargs):
            nonlocal call_count
            if call_count == 0:
                call_count += 1
                return sample_raw_response_page1
            else:
                return sample_raw_response_page2_last

        mock_client.fetch_category_games.side_effect = side_effect

        collector = ConcurrentCollector(client=mock_client, repo=mock_repo)
        result = await collector.collect_category("cat-multi")

        # Should have fetched 2 pages
        assert mock_client.fetch_category_games.call_count == 2

        # Total games across both pages
        assert result["total_fetched"] == 3  # 2 on page 1 + 1 on page 2
        assert result["total_stored"] == 3
        assert result["errors"] == []

    @pytest.mark.asyncio
    async def test_pagination_offsets(self, mock_client, mock_repo, sample_raw_response_page1, sample_raw_response_page2_last):
        """Each subsequent page should use correct offset."""
        calls_made = []
        original_call = mock_client.fetch_category_games

        async def capture_call(*args, **kwargs):
            calls_made.append(kwargs)
            if len(calls_made) == 1:
                return sample_raw_response_page1
            return sample_raw_response_page2_last

        mock_client.fetch_category_games.side_effect = capture_call

        collector = ConcurrentCollector(client=mock_client, repo=mock_repo, page_size=2)
        await collector.collect_category("cat-paging")

        assert len(calls_made) == 2
        assert calls_made[0]["offset"] == 0
        assert calls_made[0]["size"] == 2
        assert calls_made[1]["offset"] == 2  # offset advances by page_size
        assert calls_made[1]["size"] == 2


class TestErrorHandling:
    """Test that errors don't interrupt the overall collection."""

    @pytest.mark.asyncio
    async def test_api_error_recorded_but_continues(self, mock_client, mock_repo, sample_raw_response_single_page):
        """API error on one page should be recorded but not crash."""
        call_count = 0

        async def fail_then_succeed(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise Exception("API timeout")
            return sample_raw_response_single_page

        mock_client.fetch_category_games.side_effect = fail_then_succeed

        collector = ConcurrentCollector(client=mock_client, repo=mock_repo)
        result = await collector.collect_category("cat-error")

        # Should record error
        assert len(result["errors"]) >= 1
        # But still process subsequent pages
        assert result["total_stored"] == 2

    @pytest.mark.asyncio
    async def test_parse_error_handled(self, mock_client, mock_repo):
        """Invalid response that can't be parsed should be handled gracefully."""
        mock_client.fetch_category_games.return_value = {"invalid": "data"}

        collector = ConcurrentCollector(client=mock_client, repo=mock_repo)
        result = await collector.collect_category("cat-bad")

        # Should record an error
        assert len(result["errors"]) >= 1
        assert result["total_fetched"] == 0
        assert result["total_stored"] == 0


class TestStatistics:
    """Test collection statistics accuracy."""

    @pytest.mark.asyncio
    async def test_image_count_accurate(self, mock_client, mock_repo, sample_raw_response_single_page):
        """Total image count should match sum of all game images."""
        mock_client.fetch_category_games.return_value = sample_raw_response_single_page

        collector = ConcurrentCollector(client=mock_client, repo=mock_repo)
        result = await collector.collect_category("cat-img")

        # game-001 has 2 images (MASTER + SCREENSHOT), game-002 has 1 (MASTER)
        assert result["total_images"] == 3

    @pytest.mark.asyncio
    async def test_empty_page_stats(self, mock_client, mock_repo):
        """Page with no products should produce zero stats."""
        mock_client.fetch_category_games.return_value = {
            "data": {
                "categoryGridRetrieve": {
                    "pageInfo": {"totalCount": 0, "offset": 0, "size": 0, "isLast": True},
                    "products": [],
                }
            }
        }

        collector = ConcurrentCollector(client=mock_client, repo=mock_repo)
        result = await collector.collect_category("cat-empty")

        assert result["total_fetched"] == 0
        assert result["total_stored"] == 0
        assert result["total_images"] == 0
        assert result["errors"] == []


class TestConfiguration:
    """Test collector configuration options."""

    def test_max_workers_setting(self, mock_client, mock_repo):
        """max_workers should be stored as instance attribute."""
        collector = ConcurrentCollector(
            client=mock_client, repo=mock_repo, max_workers=8
        )
        assert collector.max_workers == 8

    def test_semaphore_limit_setting(self, mock_client, mock_repo):
        """semaphore_limit should be stored as instance attribute."""
        collector = ConcurrentCollector(
            client=mock_client, repo=mock_repo, semaphore_limit=5
        )
        assert collector.semaphore_limit == 5

    def test_default_values(self, mock_client, mock_repo):
        """Default values should match expected defaults."""
        collector = ConcurrentCollector(
            client=mock_client, repo=mock_repo
        )
        assert collector.max_workers == 4
        assert collector.semaphore_limit == 3
        assert collector.page_size == 24

    def test_custom_page_size(self, mock_client, mock_repo):
        """Custom page_size should be used in API calls."""
        collector = ConcurrentCollector(
            client=mock_client, repo=mock_repo, page_size=10
        )
        assert collector.page_size == 10
