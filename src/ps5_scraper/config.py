"""Configuration management using Pydantic BaseModel with YAML support.

Loads settings from config/settings.yaml with environment variable overrides.
Provides factory methods for creating configured client and database instances.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel

from ps5_scraper.api.psstore_client import PSStoreClient
from ps5_scraper.storage.database import DatabaseManager

logger = logging.getLogger(__name__)

# ─── Default values ──────────────────────────────────────────────

_DEFAULT_API_BASE_URL = "https://web.np.playstation.com/api/graphql/v1/op"
_DEFAULT_LOCALE = "zh-hant-hk"
_DEFAULT_TIMEOUT = 30
_DEFAULT_RETRY_ATTEMPTS = 3
_DEFAULT_RETRY_BACKOFF = 1.0
_DEFAULT_RPM = 60
_DEFAULT_HASH_VALUE = "4ce7d410a4db2c8b635a48c1dcec375906ff63b19dadd87e073f8fd0c0481d35"
_DEFAULT_CATEGORY_IDS = {
    "ps5_games": "4cbf39e2-5749-4970-ba81-93a489e4570c",
    "deals": "3f772501-f6f8-49b7-abac-874a88ca4897",
    "free_games": "4dfd67ab-4ed7-40b0-a937-a549aece13d0",
}
_DEFAULT_PAGE_SIZE = 24
_DEFAULT_MAX_WORKERS = 4
_DEFAULT_SEMAPHORE_LIMIT = 3
_DEFAULT_DB_PATH = "data/ps5_games.db"
_DEFAULT_WAL_MODE = True
_DEFAULT_IMAGE_ROLES = [
    "MASTER",
    "GAMEHUB_COVER_ART",
    "FOUR_BY_THREE_BANNER",
    "PORTRAIT_BANNER",
    "LOGO",
    "SCREENSHOT",
    "EDITION_KEY_ART",
    "BACKGROUND",
    "PREVIEW",
]
_DEFAULT_LOG_LEVEL = "INFO"


# ─── Safe type conversion helpers ────────────────────────────────


def _safe_int(value: str, default: int, env_key: str) -> int:
    """Safely convert a string to int, returning default on failure."""
    try:
        return int(value)
    except ValueError:
        logger.warning(
            "Invalid integer value %r for env var %s, using default %d",
            value, env_key, default,
        )
        return default


def _safe_float(value: str, default: float, env_key: str) -> float:
    """Safely convert a string to float, returning default on failure."""
    try:
        return float(value)
    except ValueError:
        logger.warning(
            "Invalid float value %r for env var %s, using default %s",
            value, env_key, default,
        )
        return default


def _safe_bool(value: str | bool | None, default: bool) -> bool:
    """Safely convert a value to bool."""
    if isinstance(value, bool):
        return value
    if value is None:
        return default
    if isinstance(value, str):
        return value.lower() in ("true", "1", "yes")
    return default


# ─── Settings class ──────────────────────────────────────────────


class Settings(BaseModel):
    """Application settings loaded from YAML file with environment variable overrides.

    Loads defaults from config/settings.yaml, then applies environment variable
    overrides. Environment variables use PS5_ prefix matching the YAML keys.

    Args:
        config_file: Path to the YAML configuration file.
            Uses defaults if the file doesn't exist.
    """

    # API settings
    api_base_url: str = _DEFAULT_API_BASE_URL
    locale: str = _DEFAULT_LOCALE
    timeout: int = _DEFAULT_TIMEOUT
    retry_attempts: int = _DEFAULT_RETRY_ATTEMPTS
    retry_backoff: float = _DEFAULT_RETRY_BACKOFF
    requests_per_minute: int = _DEFAULT_RPM

    # Hash settings
    hash_value: str = _DEFAULT_HASH_VALUE

    # Category IDs
    category_ids: dict[str, str] = _DEFAULT_CATEGORY_IDS

    # Pagination
    page_size: int = _DEFAULT_PAGE_SIZE

    # Concurrency
    max_workers: int = _DEFAULT_MAX_WORKERS
    semaphore_limit: int = _DEFAULT_SEMAPHORE_LIMIT

    # Storage
    db_path: str = _DEFAULT_DB_PATH
    wal_mode: bool = _DEFAULT_WAL_MODE

    # Images
    image_roles: list[str] = _DEFAULT_IMAGE_ROLES

    # Logging
    log_level: str = _DEFAULT_LOG_LEVEL

    def __init__(self, config_file: str = "config/settings.yaml") -> None:
        # Load YAML defaults
        yaml_data = self._load_yaml(config_file)

        # Build field values from YAML + env vars
        data = self._build_settings_dict(yaml_data)
        super().__init__(**data)

    # ─── YAML loading ────────────────────────────────────────────

    @staticmethod
    def _load_yaml(config_file: str) -> dict[str, Any]:
        """Load configuration from YAML file, returning empty dict on failure."""
        path = Path(config_file)
        if not path.exists():
            return {}
        try:
            content = path.read_text(encoding="utf-8")
            return yaml.safe_load(content) or {}
        except (yaml.YAMLError, OSError) as e:
            logger.warning("Failed to load config from %s: %s", config_file, e)
            return {}

    # ─── Environment variable helpers ────────────────────────────

    @staticmethod
    def _get_env(key: str, default: str | None = None) -> str | None:
        """Get an environment variable value."""
        return os.environ.get(key, default)

    # ─── Build settings dict from YAML + env ─────────────────────

    def _build_settings_dict(self, yaml_data: dict[str, Any]) -> dict[str, Any]:
        """Build all settings fields from YAML data with env var overrides."""
        api_yaml = yaml_data.get("api", {})
        hashes_yaml = yaml_data.get("hashes", {})
        categories_yaml = yaml_data.get("categories", {})
        pagination_yaml = yaml_data.get("pagination", {})
        concurrency_yaml = yaml_data.get("concurrency", {})
        storage_yaml = yaml_data.get("storage", {})
        images_yaml = yaml_data.get("images", {})
        logging_yaml = yaml_data.get("logging", {})

        return {
            "api_base_url": self._get_env(
                "PS5_API_BASE_URL",
                api_yaml.get("base_url", _DEFAULT_API_BASE_URL),
            ),
            "locale": self._get_env(
                "PS5_LOCALE",
                api_yaml.get("locale", _DEFAULT_LOCALE),
            ),
            "timeout": _safe_int(
                self._get_env("PS5_TIMEOUT", str(api_yaml.get("timeout", _DEFAULT_TIMEOUT))) or str(_DEFAULT_TIMEOUT),
                _DEFAULT_TIMEOUT,
                "PS5_TIMEOUT",
            ),
            "retry_attempts": _safe_int(
                self._get_env("PS5_RETRY_ATTEMPTS", str(api_yaml.get("retry_attempts", _DEFAULT_RETRY_ATTEMPTS))) or str(_DEFAULT_RETRY_ATTEMPTS),
                _DEFAULT_RETRY_ATTEMPTS,
                "PS5_RETRY_ATTEMPTS",
            ),
            "retry_backoff": _safe_float(
                self._get_env("PS5_RETRY_BACKOFF", str(api_yaml.get("retry_backoff", _DEFAULT_RETRY_BACKOFF))) or str(_DEFAULT_RETRY_BACKOFF),
                _DEFAULT_RETRY_BACKOFF,
                "PS5_RETRY_BACKOFF",
            ),
            "requests_per_minute": _safe_int(
                self._get_env("PS5_RPM", str(api_yaml.get("requests_per_minute", _DEFAULT_RPM))) or str(_DEFAULT_RPM),
                _DEFAULT_RPM,
                "PS5_RPM",
            ),
            "hash_value": self._get_env(
                "PS5_HASH_VALUE",
                hashes_yaml.get("category_grid_retrieve", _DEFAULT_HASH_VALUE),
            ) or _DEFAULT_HASH_VALUE,
            "category_ids": {
                k: v for k, v in {
                    **_DEFAULT_CATEGORY_IDS,
                    **(categories_yaml if isinstance(categories_yaml, dict) else {}),
                }.items()
            },
            "page_size": _safe_int(
                self._get_env("PS5_PAGE_SIZE", str(pagination_yaml.get("page_size", _DEFAULT_PAGE_SIZE))) or str(_DEFAULT_PAGE_SIZE),
                _DEFAULT_PAGE_SIZE,
                "PS5_PAGE_SIZE",
            ),
            "max_workers": _safe_int(
                self._get_env("PS5_MAX_WORKERS", str(concurrency_yaml.get("max_workers", _DEFAULT_MAX_WORKERS))) or str(_DEFAULT_MAX_WORKERS),
                _DEFAULT_MAX_WORKERS,
                "PS5_MAX_WORKERS",
            ),
            "semaphore_limit": _safe_int(
                self._get_env("PS5_SEMAPHORE_LIMIT", str(concurrency_yaml.get("semaphore_limit", _DEFAULT_SEMAPHORE_LIMIT))) or str(_DEFAULT_SEMAPHORE_LIMIT),
                _DEFAULT_SEMAPHORE_LIMIT,
                "PS5_SEMAPHORE_LIMIT",
            ),
            "db_path": self._get_env(
                "PS5_DB_PATH",
                storage_yaml.get("database_path", _DEFAULT_DB_PATH),
            ) or _DEFAULT_DB_PATH,
            "wal_mode": _safe_bool(
                self._get_env("PS5_WAL_MODE"),
                storage_yaml.get("wal_mode", _DEFAULT_WAL_MODE),
            ),
            "image_roles": images_yaml.get("extract_roles", _DEFAULT_IMAGE_ROLES) if images_yaml else _DEFAULT_IMAGE_ROLES,
            "log_level": self._get_env(
                "PS5_LOG_LEVEL",
                logging_yaml.get("level", _DEFAULT_LOG_LEVEL),
            ) or _DEFAULT_LOG_LEVEL,
        }

    # ─── Factory methods ─────────────────────────────────────────

    def get_psstore_client(self) -> PSStoreClient:
        """Create a PSStoreClient instance configured with these settings.

        Returns:
            A fully configured PSStoreClient ready for API calls.
        """
        return PSStoreClient(
            locale=self.locale,
            requests_per_minute=self.requests_per_minute,
            timeout=self.timeout,
            max_retries=self.retry_attempts,
        )

    def get_database(self) -> DatabaseManager:
        """Create a DatabaseManager instance configured with these settings.

        Returns:
            A DatabaseManager pointing to the configured database path.
        """
        return DatabaseManager(db_path=self.db_path)

    @classmethod
    def load_from_yaml(cls, path: str) -> Settings:
        """Alternative constructor: load from explicit YAML path.

        Args:
            path: Path to the YAML configuration file.

        Returns:
            Configured Settings instance.
        """
        return cls(config_file=path)
