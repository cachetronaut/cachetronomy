"""
Tests for schema models in types/schemas.py.
"""
import pytest
from datetime import datetime, timedelta
from cachetronomy.core.types.schemas import (
    CacheMetadata,
    CacheEntry,
    ExpiredEntry,
    AccessLogEntry,
    EvictionLogEntry,
    CustomQuery
)


class TestCacheMetadata:
    def test_cache_metadata_creation(self):
        """Test creating a CacheMetadata instance."""
        expire_at = datetime.now() + timedelta(hours=1)
        metadata = CacheMetadata(
            key="test_key",
            fmt="json",
            expire_at=expire_at,
            tags=["tag1", "tag2"],
            saved_by_profile="default",
            version=1
        )
        assert metadata.key == "test_key"
        assert metadata.fmt == "json"
        assert metadata.expire_at == expire_at
        assert metadata.tags == ["tag1", "tag2"]
        assert metadata.saved_by_profile == "default"
        assert metadata.version == 1

    def test_cache_metadata_with_none_tags(self):
        """Test that None tags are converted to default tags."""
        expire_at = datetime.now() + timedelta(hours=1)
        metadata = CacheMetadata(
            key="test_key",
            fmt="json",
            expire_at=expire_at,
            tags=None,
            saved_by_profile="default",
            version=1
        )
        # The validator should set default tags
        assert metadata.tags == ['default']

    def test_cache_metadata_tags_json_property(self):
        """Test the tags_json property."""
        expire_at = datetime.now() + timedelta(hours=1)
        metadata = CacheMetadata(
            key="test_key",
            fmt="json",
            expire_at=expire_at,
            tags=["tag1", "tag2"],
            saved_by_profile="default",
            version=1
        )
        tags_json = metadata.tags_json
        assert tags_json == '["tag1", "tag2"]'

    def test_cache_metadata_version_validation(self):
        """Test that version must be >= 1."""
        expire_at = datetime.now() + timedelta(hours=1)

        # Valid version
        metadata = CacheMetadata(
            key="test_key",
            fmt="json",
            expire_at=expire_at,
            saved_by_profile="default",
            version=2
        )
        assert metadata.version == 2

        # Invalid version
        with pytest.raises(ValueError):
            CacheMetadata(
                key="test_key",
                fmt="json",
                expire_at=expire_at,
                saved_by_profile="default",
                version=0
            )


class TestCacheEntry:
    def test_cache_entry_creation(self):
        """Test creating a CacheEntry instance."""
        expire_at = datetime.now() + timedelta(hours=1)
        entry = CacheEntry(
            key="test_key",
            fmt="json",
            expire_at=expire_at,
            tags=["tag1"],
            saved_by_profile="default",
            version=1,
            data={"some": "data"}
        )
        assert entry.key == "test_key"
        assert entry.data == {"some": "data"}


class TestExpiredEntry:
    def test_expired_entry_creation(self):
        """Test creating an ExpiredEntry instance."""
        expire_at = datetime.now() - timedelta(hours=1)
        entry = ExpiredEntry(
            key="expired_key",
            expire_at=expire_at
        )
        assert entry.key == "expired_key"
        assert entry.expire_at == expire_at


class TestAccessLogEntry:
    def test_access_log_entry_creation(self):
        """Test creating an AccessLogEntry instance."""
        now = datetime.now()
        entry = AccessLogEntry(
            key="test_key",
            access_count=10,
            last_accessed=now,
            last_accessed_by_profile="default"
        )
        assert entry.key == "test_key"
        assert entry.access_count == 10
        assert entry.last_accessed == now
        assert entry.last_accessed_by_profile == "default"

    def test_access_log_entry_is_frozen(self):
        """Test that AccessLogEntry is immutable."""
        now = datetime.now()
        entry = AccessLogEntry(
            key="test_key",
            access_count=10,
            last_accessed=now,
            last_accessed_by_profile="default"
        )

        with pytest.raises(ValueError):
            entry.access_count = 20

    def test_access_log_entry_access_count_validation(self):
        """Test that access_count must be >= 0."""
        now = datetime.now()

        # Valid
        entry = AccessLogEntry(
            key="test_key",
            access_count=0,
            last_accessed=now,
            last_accessed_by_profile="default"
        )
        assert entry.access_count == 0

        # Invalid
        with pytest.raises(ValueError):
            AccessLogEntry(
                key="test_key",
                access_count=-1,
                last_accessed=now,
                last_accessed_by_profile="default"
            )


class TestEvictionLogEntry:
    def test_eviction_log_entry_creation(self):
        """Test creating an EvictionLogEntry instance."""
        now = datetime.now()
        entry = EvictionLogEntry(
            id=1,
            key="test_key",
            evicted_at=now,
            reason="TTL expired",
            last_access_count=5,
            evicted_by_profile="default"
        )
        assert entry.id == 1
        assert entry.key == "test_key"
        assert entry.evicted_at == now
        assert entry.reason == "TTL expired"
        assert entry.last_access_count == 5
        assert entry.evicted_by_profile == "default"

    def test_eviction_log_entry_with_none_id(self):
        """Test creating an EvictionLogEntry with None id."""
        now = datetime.now()
        entry = EvictionLogEntry(
            id=None,
            key="test_key",
            evicted_at=now,
            reason="TTL expired",
            last_access_count=5,
            evicted_by_profile="default"
        )
        assert entry.id is None

    def test_eviction_log_entry_is_frozen(self):
        """Test that EvictionLogEntry is immutable."""
        now = datetime.now()
        entry = EvictionLogEntry(
            id=1,
            key="test_key",
            evicted_at=now,
            reason="TTL expired",
            last_access_count=5,
            evicted_by_profile="default"
        )

        with pytest.raises(ValueError):
            entry.reason = "Memory pressure"

    def test_eviction_log_entry_access_count_validation(self):
        """Test that last_access_count must be >= 0."""
        now = datetime.now()

        # Valid
        entry = EvictionLogEntry(
            id=1,
            key="test_key",
            evicted_at=now,
            reason="TTL expired",
            last_access_count=0,
            evicted_by_profile="default"
        )
        assert entry.last_access_count == 0

        # Invalid
        with pytest.raises(ValueError):
            EvictionLogEntry(
                id=1,
                key="test_key",
                evicted_at=now,
                reason="TTL expired",
                last_access_count=-1,
                evicted_by_profile="default"
            )


class TestCustomQuery:
    def test_custom_query_read_query(self):
        """Test creating a CustomQuery for a SELECT statement."""
        query = CustomQuery(
            query="SELECT * FROM cache WHERE key = ?",
            params=("test_key",),
            schema_type=None,
            autocommit=False
        )
        assert query.query == "SELECT * FROM cache WHERE key = ?"
        assert query.params == ("test_key",)
        assert query.schema_type is None
        assert query.autocommit is False

    def test_custom_query_write_with_autocommit(self):
        """Test creating a CustomQuery for a write statement with autocommit."""
        query = CustomQuery(
            query="INSERT INTO cache (key, value) VALUES (?, ?)",
            params=("key", "value"),
            schema_type=None,
            autocommit=True
        )
        assert query.autocommit is True

    def test_custom_query_insert_without_autocommit_raises(self):
        """Test that INSERT without autocommit raises ValueError."""
        with pytest.raises(ValueError, match="Write-query detected"):
            CustomQuery(
                query="INSERT INTO cache (key, value) VALUES (?, ?)",
                params=("key", "value"),
                schema_type=None,
                autocommit=False
            )

    def test_custom_query_update_without_autocommit_raises(self):
        """Test that UPDATE without autocommit raises ValueError."""
        with pytest.raises(ValueError, match="Write-query detected"):
            CustomQuery(
                query="UPDATE cache SET value = ? WHERE key = ?",
                params=("value", "key"),
                schema_type=None,
                autocommit=False
            )

    def test_custom_query_delete_without_autocommit_raises(self):
        """Test that DELETE without autocommit raises ValueError."""
        with pytest.raises(ValueError, match="Write-query detected"):
            CustomQuery(
                query="DELETE FROM cache WHERE key = ?",
                params=("key",),
                schema_type=None,
                autocommit=False
            )

    def test_custom_query_drop_without_autocommit_raises(self):
        """Test that DROP without autocommit raises ValueError."""
        with pytest.raises(ValueError, match="Write-query detected"):
            CustomQuery(
                query="DROP TABLE cache",
                params=(),
                schema_type=None,
                autocommit=False
            )

    def test_custom_query_alter_without_autocommit_raises(self):
        """Test that ALTER without autocommit raises ValueError."""
        with pytest.raises(ValueError, match="Write-query detected"):
            CustomQuery(
                query="ALTER TABLE cache ADD COLUMN new_col TEXT",
                params=(),
                schema_type=None,
                autocommit=False
            )

    def test_custom_query_with_leading_whitespace(self):
        """Test that query validation works with leading whitespace."""
        with pytest.raises(ValueError, match="Write-query detected"):
            CustomQuery(
                query="  \n  INSERT INTO cache VALUES (?)",
                params=("value",),
                schema_type=None,
                autocommit=False
            )

    def test_custom_query_with_uppercase(self):
        """Test that query validation is case-insensitive."""
        with pytest.raises(ValueError, match="Write-query detected"):
            CustomQuery(
                query="INSERT INTO cache VALUES (?)",
                params=("value",),
                schema_type=None,
                autocommit=False
            )
