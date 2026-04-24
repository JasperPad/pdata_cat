"""SQLite database management for PS5 HK Scraper.

Features:
- WAL (Write-Ahead Logging) mode for better concurrent read performance
- PRAGMA optimizations for performance
- Schema version tracking for future migrations
- Context manager-based connection handling
"""

from __future__ import annotations

import logging
import re
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# Allowed characters for SQL identifiers (table names, column names)
_VALID_IDENTIFIER_RE = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")


def _validate_identifier(name: str, label: str = "identifier") -> str:
    """Validate a SQL identifier against a strict whitelist.

    Only allows alphanumeric characters and underscores, must start with
    letter or underscore.

    Args:
        name: The identifier to validate.
        label: Human-readable label for error messages.

    Returns:
        The validated identifier string.

    Raises:
        ValueError: If the identifier contains invalid characters.
    """
    if not _VALID_IDENTIFIER_RE.match(name):
        raise ValueError(
            f"Invalid {label} '{name}': must contain only [a-zA-Z0-9_] "
            f"and start with [a-zA-Z_]"
        )
    return name


SCHEMA_VERSION = 2

# SQL DDL statements
CREATE_GAMES_TABLE = """
CREATE TABLE IF NOT EXISTS games (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    platforms TEXT DEFAULT '[]',
    classification TEXT DEFAULT '',
    release_date TEXT DEFAULT '',
    provider_name TEXT DEFAULT '',
    top_genre TEXT DEFAULT '',
    age_rating_label TEXT DEFAULT '',
    star_rating_score REAL DEFAULT 0.0,
    star_rating_total INTEGER DEFAULT 0,
    base_price TEXT DEFAULT '',
    discounted_price TEXT DEFAULT '',
    discount_text TEXT DEFAULT '',
    is_free INTEGER DEFAULT 0,
    is_exclusive INTEGER DEFAULT 0,
    service_branding TEXT DEFAULT '[]',
    upsell_text TEXT DEFAULT '',
    sku_count INTEGER DEFAULT 0,
    last_updated INTEGER DEFAULT 0,
    region TEXT DEFAULT 'HK',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""

CREATE_GAME_IMAGES_TABLE = """
CREATE TABLE IF NOT EXISTS game_images (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    game_id TEXT NOT NULL REFERENCES games(id) ON DELETE CASCADE,
    role TEXT NOT NULL,
    image_type TEXT NOT NULL,
    url TEXT NOT NULL,
    width INTEGER,
    height INTEGER,
    UNIQUE(game_id, role, url)
);
"""

CREATE_INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_game_images_game_id ON game_images(game_id);",
    "CREATE INDEX IF NOT EXISTS idx_games_last_updated ON games(last_updated);",
    "CREATE INDEX IF NOT EXISTS idx_games_region ON games(region);",
]

CREATE_SCHEMA_VERSION_TABLE = """
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY,
    applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""

PRAGMA_SETTINGS = {
    "journal_mode": "WAL",
    "synchronous": "NORMAL",
    "foreign_keys": "ON",
    "cache_size": -64 * 1024,  # 64 MB
    "mmap_size": 64 * 1024 * 1024,  # 64 MB
    "temp_store": "MEMORY",
}


class DatabaseManager:
    """Manages SQLite database connections and schema.

    Usage:
        db = DatabaseManager(db_path="data/games.db")
        db.initialize()

        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM games")
    """

    def __init__(self, db_path: str = "data/games.db") -> None:
        self.db_path = db_path
        self._ensure_directory()
        # Keep a reference alive for :memory: databases so data persists
        # across connections
        self._memory_keepalive_conn: sqlite3.Connection | None = None

    def _ensure_directory(self) -> None:
        """Create parent directory if it doesn't exist."""
        if self.db_path != ":memory:" and not self.db_path.startswith("file:"):
            Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)

    def __enter__(self) -> "DatabaseManager":
        """Context manager entry — initialize and return self."""
        self.initialize()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Context manager exit — no-op (connections are per-call)."""
        return None

    def _get_db_path_for_connect(self) -> str:
        """Get the actual path/URI to use for sqlite3.connect().
        
        For :memory: databases, use shared cache so connections share the same DB.
        """
        if self.db_path == ":memory:":
            return "file::memory:?cache=shared"
        return self.db_path

    def initialize(self) -> None:
        """Initialize database: create tables, indexes, set PRAGMAs.

        Safe to call multiple times — uses CREATE IF NOT EXISTS.
        """
        # For :memory: databases, keep one connection alive so data persists
        if self.db_path == ":memory:" and self._memory_keepalive_conn is None:
            self._memory_keepalive_conn = sqlite3.connect(
                "file::memory:?cache=shared"
            )

        with self._get_raw_connection() as conn:
            cursor = conn.cursor()
            
            # Set PRAGMA optimizations (internal constants only — safe)
            _VALID_PRAGMAS = {"journal_mode", "synchronous", "cache_size", "temp_store", "mmap_size", "busy_timeout", "foreign_keys"}
            for pragma, value in PRAGMA_SETTINGS.items():
                if pragma not in _VALID_PRAGMAS:
                    raise ValueError(f"Unknown PRAGMA: {pragma}")
                cursor.execute(f"PRAGMA [{pragma}] = {value}")
            
            # Create tables
            cursor.execute(CREATE_GAMES_TABLE)
            cursor.execute(CREATE_GAME_IMAGES_TABLE)
            cursor.execute(CREATE_SCHEMA_VERSION_TABLE)
            
            # ─── Schema migrations (BEFORE index creation) ──────
            # v1 → v2: Add region column if missing
            self._add_columns_if_missing("games", {"region": "TEXT DEFAULT 'HK'"})

            # Create indexes (after migrations so new columns exist)
            for index_sql in CREATE_INDEXES:
                cursor.execute(index_sql)

            # Track schema version
            cursor.execute(
                "INSERT OR IGNORE INTO schema_version (version) VALUES (?)",
                (SCHEMA_VERSION,),
            )

            conn.commit()
            logger.info("Database initialized at %s (schema v%d)", self.db_path, SCHEMA_VERSION)

    @contextmanager
    def get_connection(self):
        """Yield a connection with autocommit on exit.
        
        Usage:
            with db.get_connection() as conn:
                conn.execute(...)
        """
        conn = sqlite3.connect(self._get_db_path_for_connect())
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    @contextmanager
    def get_cursor(self):
        """Yield a cursor from a managed connection.
        
        Usage:
            with db.get_cursor() as cursor:
                cursor.execute(...)
        """
        with self.get_connection() as conn:
            yield conn.cursor()

    @contextmanager
    def _get_raw_connection(self):
        """Yield a raw connection without transaction wrapping (for init)."""
        conn = sqlite3.connect(self._get_db_path_for_connect())
        try:
            yield conn
        finally:
            conn.close()

    def _add_columns_if_missing(
        self, table_name: str, columns: dict[str, str]
    ) -> None:
        """Add missing columns to a table (for schema migrations).

        Args:
            table_name: Table to modify.
            columns: Dict of column_name → column_type definition.

        Raises:
            ValueError: If table_name or any column name contains invalid characters.
        """
        # Validate identifiers to prevent SQL injection
        _validate_identifier(table_name, "table name")
        for col_name in columns:
            _validate_identifier(col_name, "column name")

        with self._get_raw_connection() as conn:
            cursor = conn.cursor()
            # Get existing columns (table_name validated by _validate_identifier above)
            cursor.execute(f"PRAGMA table_info([{table_name}])")
            existing = {row[1] for row in cursor.fetchall()}
            
            for col_name, col_def in columns.items():
                if col_name not in existing:
                    try:
                        cursor.execute(
                            f"ALTER TABLE {table_name} ADD COLUMN {col_name} {col_def}"
                        )
                        logger.info("Added column %s to %s", col_name, table_name)
                    except sqlite3.OperationalError as e:
                        logger.warning("Failed to add column %s: %s", col_name, e)
            
            conn.commit()
