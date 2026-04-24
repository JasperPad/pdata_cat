"""Tests for CLI module (ps5_scraper.cli)."""

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import typer
from typer.testing import CliRunner

from ps5_scraper.cli import app
from ps5_scraper.config import Settings
from ps5_scraper.models.game import Game, GameImage

runner = CliRunner()


# ─── Fixtures ──────────────────────────────────────────────


@pytest.fixture()
def mock_settings():
    """Create a mock Settings instance."""
    s = MagicMock()
    s.api_base_url = "https://web.np.playstation.com/api/graphql/v1/op"
    s.locale = "zh-hant-hk"
    s.timeout = 30
    s.retry_attempts = 3
    s.retry_backoff = 1.0
    s.rpm = 200
    s.requests_per_minute = 200
    s.hash_value = "test_hash_123"
    s.category_ids = {"ps5_games": "cat_id_001", "deals": "cat_id_002", "free_games": "cat_id_003"}
    s.page_size = 24
    s.max_workers = 4
    s.semaphore_limit = 3
    s.db_path = ":memory:"
    s.wal_mode = True
    s.image_roles = ["MASTER", "SCREENSHOT"]
    s.log_level = "INFO"
    return s


@pytest.fixture()
def sample_games() -> list[Game]:
    """Sample game data for testing."""
    return [
        Game(
            id="HP0002-PPSA08784_00-GOYOTHEGAME0000",
            name="Goyo's Adventure",
            platforms=["PS5"],
            classification="FULL_GAME",
            release_date="2024-03-15",
            provider_name="Goyo Studio",
            top_genre="Adventure",
            age_rating_label="12+",
            star_rating_score=4.5,
            star_rating_total=1200,
            images=[
                GameImage(role="MASTER", type="IMAGE", url="https://example.com/master.jpg"),
                GameImage(role="SCREENSHOT", type="IMAGE", url="https://example.com/ss1.jpg"),
                GameImage(role="SCREENSHOT", type="IMAGE", url="https://example.com/ss2.jpg"),
                GameImage(role="BACKGROUND", type="IMAGE", url="https://example.com/bg.jpg"),
                GameImage(role="PREVIEW", type="VIDEO", url="https://example.com/preview.mp4"),
            ],
            sku_count=1,
            last_updated=1710460800,
        ),
        Game(
            id="HP0002-PPSA07899_00-HORIZONFW00000",
            name="Horizon Forbidden West",
            platforms=["PS5"],
            classification="FULL_GAME",
            release_date="2022-02-18",
            provider_name="Sony Interactive Entertainment",
            top_genre="Action RPG",
            age_rating_label="16+",
            star_rating_score=4.8,
            star_rating_total=15000,
            images=[
                GameImage(role="MASTER", type="IMAGE", url="https://example.com/hfw_master.jpg"),
                GameImage(role="SCREENSHOT", type="IMAGE", url="https://example.com/hfw_ss.jpg"),
            ],
            sku_count=2,
            last_updated=1645142400,
        ),
    ]


# ─── Test: Help works ─────────────────────────────────────


class TestHelp:
    """Test that --help works for all commands."""

    def test_root_help(self):
        """Root help should display available commands."""
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "collect" in result.output
        assert "export" in result.output
        assert "status" in result.output
        assert "images" in result.output

    def test_collect_help(self):
        """collect --help should show options."""
        result = runner.invoke(app, ["collect", "--help"])
        assert result.exit_code == 0
        assert "--category" in result.output or "-c" in result.output
        assert "--full" in result.output
        assert "--workers" in result.output or "-w" in result.output

    def test_export_help(self):
        """export --help should show options."""
        result = runner.invoke(app, ["export", "--help"])
        assert result.exit_code == 0
        assert "--format" in result.output or "-f" in result.output
        assert "--output" in result.output or "-o" in result.output

    def test_images_help(self):
        """images --help should show options (the core v1.0 feature)."""
        result = runner.invoke(app, ["images", "--help"])
        assert result.exit_code == 0
        assert "--game-id" in result.output
        assert "--role" in result.output
        assert "--type" in result.output
        assert "--json" in result.output

    def test_status_help(self):
        """status --help should work."""
        result = runner.invoke(app, ["status", "--help"])
        assert result.exit_code == 0


# ─── Test: collect command ─────────────────────────────────


class TestCollectCommand:
    """Test the collect command."""

    @patch("ps5_scraper.cli.Settings")
    @patch("ps5_scraper.cli.CollectionPipeline")
    def test_collect_calls_pipeline(self, mock_pipeline_cls, mock_settings_cls, mock_settings):
        """collect should call pipeline.run_full_collection()."""
        mock_settings_cls.return_value = mock_settings

        mock_pipeline = MagicMock()
        mock_pipeline.run_full_collection = MagicMock(
            return_value={
                "category": "ps5_games",
                "success": True,
                "total_fetched": 48,
                "total_stored": 48,
                "total_images": 96,
                "errors": [],
                "duration_seconds": 12.5,
            }
        )
        mock_pipeline_cls.return_value = mock_pipeline

        result = runner.invoke(app, ["collect"])

        assert result.exit_code == 0
        mock_pipeline.run_full_collection.assert_called_once_with("ps5_games", full_mode=False)
        assert "48" in result.output  # total_fetched shown

    @patch("ps5_scraper.cli.Settings")
    @patch("ps5_scraper.cli.CollectionPipeline")
    def test_collect_with_category(self, mock_pipeline_cls, mock_settings_cls, mock_settings):
        """collect -c deals should use deals category."""
        mock_settings_cls.return_value = mock_settings

        mock_pipeline = MagicMock()
        mock_pipeline.run_full_collection = MagicMock(return_value={
            "category": "deals",
            "success": True,
            "total_fetched": 10,
            "total_stored": 10,
            "total_images": 20,
            "errors": [],
            "duration_seconds": 5.0,
        })
        mock_pipeline_cls.return_value = mock_pipeline

        result = runner.invoke(app, ["collect", "-c", "deals"])

        assert result.exit_code == 0
        mock_pipeline.run_full_collection.assert_called_once_with("deals", full_mode=False)

    @patch("ps5_scraper.cli.Settings")
    @patch("ps5_scraper.cli.CollectionPipeline")
    def test_collect_with_full_mode(self, mock_pipeline_cls, mock_settings_cls, mock_settings):
        """collect --full should pass full_mode=True."""
        mock_settings_cls.return_value = mock_settings

        mock_pipeline = MagicMock()
        mock_pipeline.run_full_collection = MagicMock(return_value={
            "category": "ps5_games",
            "success": True,
            "total_fetched": 100,
            "total_stored": 100,
            "total_images": 200,
            "errors": [],
            "duration_seconds": 25.0,
        })
        mock_pipeline_cls.return_value = mock_pipeline

        result = runner.invoke(app, ["collect", "--full"])

        assert result.exit_code == 0
        # Check full_mode was passed as keyword arg
        call_kwargs = mock_pipeline.run_full_collection.call_args
        assert call_kwargs.kwargs.get("full_mode") is True

    @patch("ps5_scraper.cli.Settings")
    @patch("ps5_scraper.cli.CollectionPipeline")
    def test_collect_shows_errors(self, mock_pipeline_cls, mock_settings_cls, mock_settings):
        """collect should show errors when collection fails partially."""
        mock_settings_cls.return_value = mock_settings

        mock_pipeline = MagicMock()
        mock_pipeline.run_full_collection = MagicMock(return_value={
            "category": "ps5_games",
            "success": False,
            "total_fetched": 46,
            "total_stored": 46,
            "total_images": 90,
            "errors": ["Rate limited on page 3"],
            "duration_seconds": 15.0,
        })
        mock_pipeline_cls.return_value = mock_pipeline

        result = runner.invoke(app, ["collect"])

        assert result.exit_code == 0  # Should not crash
        # Output contains error info (Chinese: 错误)
        assert "error" in result.output.lower() or "fail" in result.output.lower() or "\u9519\u8bef" in result.output


# ─── Test: export command ──────────────────────────────────


class TestExportCommand:
    """Test the export command."""

    @patch("ps5_scraper.cli.Settings")
    @patch("ps5_scraper.cli.DatabaseManager")
    @patch("ps5_scraper.cli.GameRepository")
    def test_export_json(self, mock_repo_cls, mock_db_cls, mock_settings_cls, mock_settings, sample_games):
        """export -f json should output JSON format."""
        mock_settings_cls.return_value = mock_settings

        mock_db = MagicMock()
        mock_db_cls.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_db_cls.return_value.__exit__ = MagicMock(return_value=False)

        mock_repo = MagicMock()
        mock_repo.get_all.return_value = sample_games
        mock_repo_cls.return_value = mock_repo

        result = runner.invoke(app, ["export", "-f", "json"])

        assert result.exit_code == 0
        data = json.loads(result.output)
        assert len(data) == 2
        assert data[0]["name"] == "Goyo's Adventure"
        assert data[1]["name"] == "Horizon Forbidden West"

    @patch("ps5_scraper.cli.Settings")
    @patch("ps5_scraper.cli.DatabaseManager")
    @patch("ps5_scraper.cli.GameRepository")
    def test_export_json_to_file(self, mock_repo_cls, mock_db_cls, mock_settings_cls, mock_settings, sample_games, tmp_path):
        """export -f json -o <path> should write to file."""
        mock_settings_cls.return_value = mock_settings

        mock_db = MagicMock()
        mock_db_cls.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_db_cls.return_value.__exit__ = MagicMock(return_value=False)

        mock_repo = MagicMock()
        mock_repo.get_all.return_value = sample_games
        mock_repo_cls.return_value = mock_repo

        output_file = str(tmp_path / "output.json")
        result = runner.invoke(app, ["export", "-f", "json", "-o", output_file])

        assert result.exit_code == 0
        assert Path(output_file).exists()
        file_data = json.loads(Path(output_file).read_text())
        assert len(file_data) == 2

    @patch("ps5_scraper.cli.Settings")
    @patch("ps5_scraper.cli.DatabaseManager")
    @patch("ps5_scraper.cli.GameRepository")
    def test_export_empty_database(self, mock_repo_cls, mock_db_cls, mock_settings_cls, mock_settings):
        """export with empty database should show message and exit 0."""
        mock_settings_cls.return_value = mock_settings

        mock_db = MagicMock()
        mock_db_cls.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_db_cls.return_value.__exit__ = MagicMock(return_value=False)

        mock_repo = MagicMock()
        mock_repo.get_all.return_value = []
        mock_repo_cls.return_value = mock_repo

        result = runner.invoke(app, ["export"])

        assert result.exit_code == 0
        assert "empty" in result.output.lower() or "no data" in result.output.lower() or "\u6ca1\u6709" in result.output

    @patch("ps5_scraper.cli.Settings")
    @patch("ps5_scraper.cli.DatabaseManager")
    @patch("ps5_scraper.cli.GameRepository")
    def test_export_invalid_format(self, mock_repo_cls, mock_db_cls, mock_settings_cls, mock_settings, sample_games):
        """export with invalid format should exit with error."""
        mock_settings_cls.return_value = mock_settings

        mock_db = MagicMock()
        mock_db_cls.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_db_cls.return_value.__exit__ = MagicMock(return_value=False)

        mock_repo = MagicMock()
        mock_repo.get_all.return_value = sample_games
        mock_repo_cls.return_value = mock_repo

        result = runner.invoke(app, ["export", "-f", "xml"])

        assert result.exit_code != 0
        # typer.Exit may output to stderr; just verify it failed


# ─── Test: status command ─────────────────────────────────


class TestStatusCommand:
    """Test the status command."""

    @patch("ps5_scraper.cli.Settings")
    @patch("ps5_scraper.cli.DatabaseManager")
    @patch("ps5_scraper.cli.GameRepository")
    def test_status_shows_stats(self, mock_repo_cls, mock_db_cls, mock_settings_cls, mock_settings):
        """status should show game count, image count, etc."""
        mock_settings_cls.return_value = mock_settings

        mock_db = MagicMock()
        mock_db_cls.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_db_cls.return_value.__exit__ = MagicMock(return_value=False)

        mock_repo = MagicMock()
        mock_repo.get_count.return_value = 42
        mock_repo.get_all.return_value = []
        mock_repo_cls.return_value = mock_repo

        result = runner.invoke(app, ["status"])

        assert result.exit_code == 0
        assert "42" in result.output

    @patch("ps5_scraper.cli.Settings")
    @patch("ps5_scraper.cli.DatabaseManager")
    @patch("ps5_scraper.cli.GameRepository")
    def test_status_empty(self, mock_repo_cls, mock_db_cls, mock_settings_cls, mock_settings):
        """status with empty database should show 0 games."""
        mock_settings_cls.return_value = mock_settings

        mock_db = MagicMock()
        mock_db_cls.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_db_cls.return_value.__exit__ = MagicMock(return_value=False)

        mock_repo = MagicMock()
        mock_repo.get_count.return_value = 0
        mock_repo.get_all.return_value = []
        mock_repo_cls.return_value = mock_repo

        result = runner.invoke(app, ["status"])

        assert result.exit_code == 0
        assert "0" in result.output


# ─── Test: images command (v1.0 core feature) ─────────────


class TestImagesCommand:
    """Test the images command — the core selling point of v1.0."""

    @patch("ps5_scraper.cli.Settings")
    @patch("ps5_scraper.cli.DatabaseManager")
    @patch("ps5_scraper.cli.GameRepository")
    def test_images_by_game_id(self, mock_repo_cls, mock_db_cls, mock_settings_cls, mock_settings, sample_games):
        """images --game-id <id> should list all images for that game."""
        mock_settings_cls.return_value = mock_settings

        mock_db = MagicMock()
        mock_db_cls.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_db_cls.return_value.__exit__ = MagicMock(return_value=False)

        mock_repo = MagicMock()
        game = sample_games[0]
        mock_repo.get_by_id.return_value = game
        mock_repo.get_images.return_value = game.images
        mock_repo_cls.return_value = mock_repo

        result = runner.invoke(app, ["images", "--game-id", game.id])

        assert result.exit_code == 0
        assert "master.jpg" in result.output.lower() or "MASTER" in result.output
        assert str(len(game.images)) in result.output  # Should show image count

    @patch("ps5_scraper.cli.Settings")
    @patch("ps5_scraper.cli.DatabaseManager")
    @patch("ps5_scraper.cli.GameRepository")
    def test_images_filter_by_role(self, mock_repo_cls, mock_db_cls, mock_settings_cls, mock_settings, sample_games):
        """images --game-id <id> --role SCREENSHOT should filter by role."""
        mock_settings_cls.return_value = mock_settings

        mock_db = MagicMock()
        mock_db_cls.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_db_cls.return_value.__exit__ = MagicMock(return_value=False)

        mock_repo = MagicMock()
        game = sample_games[0]
        mock_repo.get_by_id.return_value = game
        mock_repo.get_images.return_value = [img for img in game.images if img.role == "SCREENSHOT"]
        mock_repo_cls.return_value = mock_repo

        result = runner.invoke(app, ["images", "--game-id", game.id, "--role", "SCREENSHOT"])

        assert result.exit_code == 0
        # Should only show SCREENSHOT images (2 out of 5)
        assert "SCREENSHOT" in result.output

    @patch("ps5_scraper.cli.Settings")
    @patch("ps5_scraper.cli.DatabaseManager")
    @patch("ps5_scraper.cli.GameRepository")
    def test_images_filter_by_type(self, mock_repo_cls, mock_db_cls, mock_settings_cls, mock_settings, sample_games):
        """images --game-id <id> --type IMAGE should filter by type."""
        mock_settings_cls.return_value = mock_settings

        mock_db = MagicMock()
        mock_db_cls.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_db_cls.return_value.__exit__ = MagicMock(return_value=False)

        mock_repo = MagicMock()
        game = sample_games[0]
        mock_repo.get_by_id.return_value = game
        mock_repo.get_images.return_value = [img for img in game.images if img.type == "IMAGE"]
        mock_repo_cls.return_value = mock_repo

        result = runner.invoke(app, ["images", "--game-id", game.id, "--type", "IMAGE"])

        assert result.exit_code == 0
        # 4 IMAGE types out of 5 (1 is VIDEO)
        assert "VIDEO" not in result.output or "preview.mp4" not in result.output.lower()

    @patch("ps5_scraper.cli.Settings")
    @patch("ps5_scraper.cli.DatabaseManager")
    @patch("ps5_scraper.cli.GameRepository")
    def test_images_json_output(self, mock_repo_cls, mock_db_cls, mock_settings_cls, mock_settings, sample_games):
        """images --game-id <id> --json should output JSON format."""
        mock_settings_cls.return_value = mock_settings

        mock_db = MagicMock()
        mock_db_cls.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_db_cls.return_value.__exit__ = MagicMock(return_value=False)

        mock_repo = MagicMock()
        game = sample_games[0]
        mock_repo.get_by_id.return_value = game
        mock_repo.get_images.return_value = game.images
        mock_repo_cls.return_value = mock_repo

        result = runner.invoke(app, ["images", "--game-id", game.id, "--json"])

        assert result.exit_code == 0
        data = json.loads(result.output)
        assert isinstance(data, list)
        assert len(data) == len(game.images)
        assert data[0]["role"] == "MASTER"
        assert data[0]["url"] == "https://example.com/master.jpg"

    @patch("ps5_scraper.cli.Settings")
    @patch("ps5_scraper.cli.DatabaseManager")
    @patch("ps5_scraper.cli.GameRepository")
    def test_images_game_not_found(self, mock_repo_cls, mock_db_cls, mock_settings_cls, mock_settings):
        """images with non-existent game ID should show error message."""
        mock_settings_cls.return_value = mock_settings

        mock_db = MagicMock()
        mock_db_cls.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_db_cls.return_value.__exit__ = MagicMock(return_value=False)

        mock_repo = MagicMock()
        mock_repo.get_by_id.return_value = None
        mock_repo.get_images.return_value = []
        mock_repo_cls.return_value = mock_repo

        result = runner.invoke(app, ["images", "--game-id", "NONEXISTENT_ID"])

        assert result.exit_code == 0  # Should not crash
        # Output: "未找到游戏 ID: NONEXISTENT_ID"
        assert "\u672a\u627e\u5230" in result.output or "not found" in result.output.lower() or "no game" in result.output.lower()

    @patch("ps5_scraper.cli.Settings")
    @patch("ps5_scraper.cli.DatabaseManager")
    @patch("ps5_scraper.cli.GameRepository")
    def test_images_no_filters_lists_all(self, mock_repo_cls, mock_db_cls, mock_settings_cls, mock_settings, sample_games):
        """images without filters should list all games with image counts."""
        mock_settings_cls.return_value = mock_settings

        mock_db = MagicMock()
        mock_db_cls.return_value.__enter__ = MagicMock(return_value=mock_db)
        mock_db_cls.return_value.__exit__ = MagicMock(return_value=False)

        mock_repo = MagicMock()
        mock_repo.get_all.return_value = sample_games
        mock_repo.get_count.return_value = len(sample_games)
        mock_repo_cls.return_value = mock_repo

        result = runner.invoke(app, ["images"])

        assert result.exit_code == 0
        # Should show all games
        assert "Goyo" in result.output or "Horizon" in result.output
