"""Tests for DatabaseManager: SQLite connection, WAL mode, schema management."""

import sqlite3
import tempfile
from pathlib import Path

import pytest


@pytest.fixture
def db_path(tmp_path):
    """Create a temporary database file path."""
    return str(tmp_path / "test.db")


@pytest.fixture
def db_manager(db_path):
    """Create a DatabaseManager instance with temp path."""
    from ps5_scraper.storage.database import DatabaseManager
    return DatabaseManager(db_path=db_path)


class TestDatabaseInitialization:
    """Test database initialization and table creation."""

    def test_create_tables(self, db_manager):
        """Should create games and game_images tables on initialize()."""
        db_manager.initialize()

        with db_manager.get_connection() as conn:
            cursor = conn.cursor()
            # Check games table exists
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='games'"
            )
            assert cursor.fetchone() is not None

            # Check game_images table exists
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='game_images'"
            )
            assert cursor.fetchone() is not None

    def test_games_table_schema(self, db_manager):
        """Games table should have all required columns."""
        db_manager.initialize()
        with db_manager.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("PRAGMA table_info(games)")
            columns = {row[1] for row in cursor.fetchall()}
            
            expected = {
                "id", "name", "platforms", "classification",
                "release_date", "provider_name", "top_genre",
                "age_rating_label", "star_rating_score", "star_rating_total",
                "base_price", "discounted_price", "discount_text",
                "is_free", "is_exclusive", "service_branding",
                "upsell_text", "sku_count", "last_updated",
                "region",  # v2.0: multi-region support
                "created_at", "updated_at",
            }
            assert columns == expected

    def test_game_images_table_schema(self, db_manager):
        """game_images table should have correct columns."""
        db_manager.initialize()
        with db_manager.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("PRAGMA table_info(game_images)")
            columns = {row[1] for row in cursor.fetchall()}
            
            expected = {"id", "game_id", "role", "image_type", "url", "width", "height"}
            assert expected.issubset(columns)

    def test_wal_mode_enabled(self, db_manager):
        """WAL journal mode should be enabled after initialization."""
        db_manager.initialize()
        with db_manager.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("PRAGMA journal_mode")
            result = cursor.fetchone()[0]
            assert result.lower() == "wal"

    def test_schema_version_table_exists(self, db_manager):
        """schema_version table should exist."""
        db_manager.initialize()
        with db_manager.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='schema_version'"
            )
            assert cursor.fetchone() is not None

    def test_schema_version_value(self, db_manager):
        """Schema version should be set to SCHEMA_VERSION (2)."""
        from ps5_scraper.storage.database import SCHEMA_VERSION
        assert SCHEMA_VERSION == 2
        db_manager.initialize()
        with db_manager.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT MAX(version) FROM schema_version")
            version = cursor.fetchone()[0]
            assert version == SCHEMA_VERSION

    def test_unique_constraint_on_game_images(self, db_manager):
        """game_images should have UNIQUE(game_id, role, url) constraint."""
        db_manager.initialize()
        with db_manager.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT sql FROM sqlite_master WHERE name='game_images'"
            )
            create_sql = cursor.fetchone()[0]
            assert "UNIQUE" in create_sql.upper()
            assert "game_id" in create_sql
            assert "role" in create_sql
            assert "url" in create_sql

    def test_foreign_key_cascade(self, db_manager):
        """game_images should have ON DELETE CASCADE to games."""
        db_manager.initialize()
        with db_manager.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT sql FROM sqlite_master WHERE name='game_images'"
            )
            create_sql = cursor.fetchone()[0].upper()
            assert "CASCADE" in create_sql

    def test_indexes_created(self, db_manager):
        """Expected indexes should be created."""
        db_manager.initialize()
        with db_manager.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='index' "
                "AND name IN ('idx_game_images_game_id', 'idx_games_last_updated')"
            )
            indexes = [row[0] for row in cursor.fetchall()]
            assert "idx_game_images_game_id" in indexes
            assert "idx_games_last_updated" in indexes


class TestDuplicateInitialization:
    """Test that calling initialize() multiple times doesn't error."""

    def test_double_init_no_error(self, db_manager):
        """Calling initialize() twice should not raise an exception."""
        db_manager.initialize()
        db_manager.initialize()  # Should not raise
        # Tables should still work
        with db_manager.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM games")
            assert cursor.fetchone()[0] == 0

    def test_triple_init_no_error(self, db_manager):
        """Even three times should be fine."""
        db_manager.initialize()
        db_manager.initialize()
        db_manager.initialize()


class TestConnectionManagement:
    """Test context manager-based connection handling."""

    def test_get_connection_context_manager(self, db_manager):
        """get_connection() should work as context manager."""
        db_manager.initialize()
        with db_manager.get_connection() as conn:
            assert isinstance(conn, sqlite3.Connection)
            cursor = conn.cursor()
            cursor.execute("SELECT 1")
            assert cursor.fetchone()[0] == 1

    def test_get_cursor_context_manager(self, db_manager):
        """get_cursor() should work as context manager."""
        db_manager.initialize()
        with db_manager.get_cursor() as cursor:
            assert cursor is not None
            cursor.execute("SELECT COUNT(*) FROM games")
            count = cursor.fetchone()[0]
            assert count >= 0

    def test_connection_auto_commit(self, db_manager):
        """Changes within context manager should be committed."""
        db_manager.initialize()
        with db_manager.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO games (id, name) VALUES (?, ?)",
                ("test-001", "Test Game"),
            )

        # Verify data persists outside the context
        with db_manager.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM games WHERE id=?", ("test-001",))
            assert cursor.fetchone()[0] == "Test Game"


class TestDatabasePath:
    """Test database path handling."""

    def test_custom_db_path(self, tmp_path):
        """Database should be created at custom path."""
        custom_path = str(tmp_path / "custom" / "data.db")
        from ps5_scraper.storage.database import DatabaseManager
        db = DatabaseManager(db_path=custom_path)
        db.initialize()
        
        assert Path(custom_path).exists()

    def test_in_memory_database(self):
        """Support :memory: databases for testing."""
        from ps5_scraper.storage.database import DatabaseManager
        db = DatabaseManager(db_path=":memory:")
        db.initialize()

        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='games'")
            assert cursor.fetchone() is not None


# ─── v2.0: Multi-region Schema (v2) ──────────────────────────────


class TestSchemaV2RegionColumn:
    """Test that Schema v2 includes the region column."""

    def test_games_table_has_region_column(self, db_manager):
        """Games table should have 'region' column with default 'hk'."""
        db_manager.initialize()
        with db_manager.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("PRAGMA table_info(games)")
            columns = {row[1]: row[2] for row in cursor.fetchall()}  # name -> type

            assert "region" in columns
            # Should be TEXT type
            assert "TEXT" in columns["region"].upper()

    def test_region_index_exists(self, db_manager):
        """Should have index on games(region) for efficient filtering."""
        db_manager.initialize()
        with db_manager.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='index' "
                "AND name='idx_games_region'"
            )
            result = cursor.fetchone()
            assert result is not None

    def test_schema_version_is_2(self, db_manager):
        """Schema version should be 2 after v2.0 upgrade."""
        from ps5_scraper.storage.database import SCHEMA_VERSION
        assert SCHEMA_VERSION == 2
        db_manager.initialize()
        with db_manager.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT MAX(version) FROM schema_version")
            version = cursor.fetchone()[0]
            assert version == 2

    def test_migration_from_v1_adds_region(self, tmp_path):
        """Migrating an existing v1 DB should add the region column."""
        import shutil
        from ps5_scraper.storage.database import DatabaseManager

        # Step 1: Create a v1-style database manually
        v1_db_path = str(tmp_path / "v1.db")
        conn = sqlite3.connect(v1_db_path)
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS games (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                platforms TEXT DEFAULT '[]',
                last_updated INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS schema_version (
                version INTEGER PRIMARY KEY,
                applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)
        cursor.execute("INSERT INTO schema_version (version) VALUES (1)")
        cursor.execute("INSERT INTO games (id, name) VALUES ('test-001', 'Old Game')")
        conn.commit()
        conn.close()

        # Step 2: Initialize with DatabaseManager (should migrate)
        db = DatabaseManager(db_path=v1_db_path)
        db.initialize()

        # Verify migration happened
        with db.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("PRAGMA table_info(games)")
            columns = {row[1] for row in cursor.fetchall()}
            assert "region" in columns

            # Old data should still be there
            cursor.execute("SELECT name FROM games WHERE id=?", ("test-001",))
            assert cursor.fetchone()[0] == "Old Game"

    def test_region_default_value_is_hk(self, db_manager):
        """New rows should default region to 'HK' if not specified."""
        db_manager.initialize()
        with db_manager.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO games (id, name) VALUES (?, ?)",
                ("auto-region-test", "Auto Region"),
            )
            cursor.execute("SELECT region FROM games WHERE id=?", ("auto-region-test",))
            region = cursor.fetchone()[0]
            # Default should be HK (from column DEFAULT)
            assert region == "HK"
