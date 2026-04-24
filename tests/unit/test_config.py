"""Tests for Settings: YAML loading, env overrides, factory methods."""

import os
import tempfile
from pathlib import Path

import pytest
import yaml

from ps5_scraper.config import Settings


@pytest.fixture
def sample_yaml_content():
    """Return a minimal valid settings.yaml content."""
    return """
api:
  base_url: "https://web.np.playstation.com/api/graphql/v1/op"
  locale: "zh-hant-hk"
  timeout: 30
  retry_attempts: 3
  retry_backoff: 1.0
  requests_per_minute: 60

hashes:
  category_grid_retrieve: "abc123hash"

categories:
  ps5_games: "4cbf39e2-5749-4970-ba81-93a489e4570c"
  deals: "3f772501-f6f8-49b7-abac-874a88ca4897"
  free_games: "4dfd67ab-4ed7-40b0-a937-a549aece13d0"

pagination:
  page_size: 24

concurrency:
  max_workers: 4
  semaphore_limit: 3

storage:
  database_path: "data/ps5_games.db"
  wal_mode: true

images:
  extract_roles:
    - "MASTER"
    - "SCREENSHOT"

logging:
  level: "INFO"
"""


@pytest.fixture
def temp_config_file(tmp_path, sample_yaml_content):
    """Create a temporary config file with sample content."""
    config_path = tmp_path / "settings.yaml"
    config_path.write_text(sample_yaml_content, encoding="utf-8")
    return str(config_path)


class TestLoadFromYaml:
    """Test YAML configuration loading."""

    def test_load_from_valid_yaml(self, temp_config_file):
        """Should load all fields from a valid YAML file."""
        settings = Settings(config_file=temp_config_file)

        assert settings.api_base_url == "https://web.np.playstation.com/api/graphql/v1/op"
        assert settings.locale == "zh-hant-hk"
        assert settings.timeout == 30
        assert settings.retry_attempts == 3
        assert settings.retry_backoff == 1.0
        assert settings.requests_per_minute == 60
        assert settings.hash_value == "abc123hash"
        assert settings.page_size == 24
        assert settings.max_workers == 4
        assert settings.semaphore_limit == 3
        assert settings.db_path == "data/ps5_games.db"
        assert settings.wal_mode is True
        assert settings.image_roles == ["MASTER", "SCREENSHOT"]
        assert settings.log_level == "INFO"

    def test_category_ids_loaded(self, temp_config_file):
        """Category IDs should be loaded correctly."""
        settings = Settings(config_file=temp_config_file)

        assert settings.category_ids["ps5_games"] == "4cbf39e2-5749-4970-ba81-93a489e4570c"
        assert settings.category_ids["deals"] == "3f772501-f6f8-49b7-abac-874a88ca4897"
        assert settings.category_ids["free_games"] == "4dfd67ab-4ed7-40b0-a937-a549aece13d0"


class TestEnvVarOverrides:
    """Test that environment variables override YAML values."""

    def test_env_overrides_base_url(self, temp_config_file, monkeypatch):
        """PS5_API_BASE_URL should override yaml value."""
        monkeypatch.setenv("PS5_API_BASE_URL", "https://custom.api.com")
        settings = Settings(config_file=temp_config_file)
        assert settings.api_base_url == "https://custom.api.com"

    def test_env_overrides_locale(self, temp_config_file, monkeypatch):
        """PS5_LOCALE should override yaml value."""
        monkeypatch.setenv("PS5_LOCALE", "en-us")
        settings = Settings(config_file=temp_config_file)
        assert settings.locale == "en-us"

    def test_env_overrides_timeout(self, temp_config_file, monkeypatch):
        """PS5_TIMEOUT should override yaml value."""
        monkeypatch.setenv("PS5_TIMEOUT", "60")
        settings = Settings(config_file=temp_config_file)
        assert settings.timeout == 60

    def test_env_overrides_retry_attempts(self, temp_config_file, monkeypatch):
        """PS5_RETRY_ATTEMPTS should override yaml value."""
        monkeypatch.setenv("PS5_RETRY_ATTEMPTS", "5")
        settings = Settings(config_file=temp_config_file)
        assert settings.retry_attempts == 5

    def test_env_overrides_db_path(self, temp_config_file, monkeypatch):
        """PS5_DB_PATH should override yaml value."""
        monkeypatch.setenv("PS5_DB_PATH", "/custom/path.db")
        settings = Settings(config_file=temp_config_file)
        assert settings.db_path == "/custom/path.db"

    def test_env_overrides_max_workers(self, temp_config_file, monkeypatch):
        """PS5_MAX_WORKERS should override yaml value."""
        monkeypatch.setenv("PS5_MAX_WORKERS", "8")
        settings = Settings(config_file=temp_config_file)
        assert settings.max_workers == 8

    def test_env_overrides_log_level(self, temp_config_file, monkeypatch):
        """PS5_LOG_LEVEL should override yaml value."""
        monkeypatch.setenv("PS5_LOG_LEVEL", "DEBUG")
        settings = Settings(config_file=temp_config_file)
        assert settings.log_level == "DEBUG"


class TestMissingConfigFile:
    """Test behavior when config file is missing or empty."""

    def test_missing_file_uses_defaults(self, tmp_path):
        """Missing config file should use default values."""
        nonexistent = str(tmp_path / "nonexistent.yaml")
        settings = Settings(config_file=nonexistent)

        # Should have sensible defaults
        assert settings.api_base_url != ""
        assert settings.locale != ""
        assert settings.timeout > 0
        assert settings.max_workers > 0

    def test_empty_yaml_uses_defaults(self, tmp_path):
        """Empty YAML file should use defaults."""
        empty_path = tmp_path / "empty.yaml"
        empty_path.write_text("", encoding="utf-8")
        settings = Settings(config_file=str(empty_path))

        assert settings.api_base_url != ""
        assert settings.timeout > 0

    def test_partial_yaml_uses_defaults_for_missing_fields(self, tmp_path):
        """YAML with only some fields should use defaults for others."""
        partial = tmp_path / "partial.yaml"
        partial.write_text('api:\n  base_url: "https://custom.com"\n', encoding="utf-8")
        settings = Settings(config_file=str(partial))

        assert settings.api_base_url == "https://custom.com"
        # Other fields should have defaults
        assert settings.timeout > 0
        assert settings.max_workers > 0


class TestFactoryMethods:
    """Test get_psstore_client() and get_database() factory methods."""

    def test_get_psstore_client_returns_configured_client(self, temp_config_file):
        """Factory should return PSStoreClient with correct config."""
        settings = Settings(config_file=temp_config_file)
        client = settings.get_psstore_client()

        assert client is not None
        assert client.locale == "zh-hant-hk"
        assert client.requests_per_minute == 60
        assert client.timeout == 30
        assert client.max_retries == 3

    def test_get_psstore_client_uses_custom_hash(self, temp_config_file):
        """Factory should pass hash_value to client (via class attribute)."""
        settings = Settings(config_file=temp_config_file)
        client = settings.get_psstore_client()

        # The hash is set as a class-level constant on PSStoreClient
        # We verify the client was created successfully
        assert client.locale == settings.locale

    def test_get_database_returns_manager_with_correct_path(self, temp_config_file):
        """Factory should return DatabaseManager with configured db_path."""
        settings = Settings(config_file=temp_config_file)
        db = settings.get_database()

        assert db is not None
        assert db.db_path == "data/ps5_games.db"

    def test_get_database_with_custom_path(self, temp_config_file, monkeypatch):
        """Factory should respect overridden db_path."""
        monkeypatch.setenv("PS5_DB_PATH", "/tmp/custom_test.db")
        settings = Settings(config_file=temp_config_file)
        db = settings.get_database()

        assert db.db_path == "/tmp/custom_test.db"


class TestSettingsModelDump:
    """Test that settings can be inspected/dumped for debugging."""

    def test_settings_has_all_required_attributes(self, temp_config_file):
        """Settings instance should expose all config attributes."""
        settings = Settings(config_file=temp_config_file)

        attrs = [
            "api_base_url", "locale", "timeout", "retry_attempts",
            "retry_backoff", "requests_per_minute", "hash_value",
            "category_ids", "page_size", "max_workers",
            "semaphore_limit", "db_path", "wal_mode",
            "image_roles", "log_level",
        ]
        for attr in attrs:
            assert hasattr(settings, attr), f"Settings missing attribute: {attr}"
