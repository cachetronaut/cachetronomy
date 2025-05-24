from typing import Protocol

from cachetronomy.core.types.profiles import Profile
from cachetronomy.core.types.schemas import (
    CacheEntry,
    CacheMetadata,
    ExpiredEntry,
    AccessLogEntry,
    EvictionLogEntry,
)

class StoreProtocol(Protocol):
    def get(self, key: str) -> CacheEntry | None: 
        pass
    def set(self, entry: CacheEntry) -> None: 
        pass
    def delete(self, key: str) -> None: 
        pass
    def clear_all(self) -> None: 
        pass
    def clear_expired(self) -> list[ExpiredEntry]: 
        pass
    def clear_by_tags(
        self, 
        tags: list[str], 
        exact_match: bool = False
    ) -> list[str]: 
        pass
    def clear_by_profile(self, profile_name: str) -> list[str]: 
        pass
    def keys(self) -> list[str] | None: 
        pass
    def items(self) -> list[CacheEntry] | None: 
        pass
    def metadata(self) -> list[CacheMetadata] | None: 
        pass
    def key_metadata(self, key: str) -> CacheMetadata | None: 
        pass
    def update_profile_settings(
        self,
        name: str,
        time_to_live: int,
        tags: list[str],
        ttl_cleanup_interval: int,
        memory_based_eviction: bool,
        free_memory_target: float,
        memory_cleanup_interval: int,
        max_items_in_memory: int
    ) -> None: 
        pass
    def profile(self, name: str) -> Profile | None: 
        pass
    def list_profiles(self) -> list[Profile] | None: 
        pass
    def delete_profile(self, name: str) -> None: 
        pass
    def log_access(self, entry: AccessLogEntry, batch: bool = True) -> None: 
        pass
    def log_access_batch(self, entries: set[AccessLogEntry]) -> None: 
        pass
    def stats(self, limit: int = 10) -> list[AccessLogEntry] | None: 
        pass
    def key_access_logs(self, key: str) -> AccessLogEntry | None: 
        pass
    def access_logs(self) -> list[AccessLogEntry] | None: 
        pass
    def delete_access_logs(self, key: str) -> None: 
        pass
    def clear_access_logs(self) -> None: 
        pass
    def log_eviction(
        self, 
        entry: EvictionLogEntry, 
        batch: bool = True
    ) -> None: 
        pass
    def log_eviction_batch(self, entries: set[EvictionLogEntry]) -> None: 
        pass
    def eviction_logs(
        self, 
        limit: int = 1000
    ) -> list[EvictionLogEntry] | None: 
        pass
    def clear_eviction_logs(self) -> None: 
        pass


class AsyncStoreProtocol(Protocol):
    async def init(self) -> None: 
        pass
    async def close(self) -> None: 
        pass
    async def get(self, key: str) -> CacheEntry | None: 
        pass
    async def set(self, entry: CacheEntry) -> None: 
        pass
    async def delete(self, key: str) -> None: 
        pass
    async def delete_all(self) -> None: 
        pass
    async def clear_expired(self) -> list[ExpiredEntry] | None: 
        pass
    async def clear_by_tags(
        self, 
        tags: list[str], 
        exact_match: bool = False
    ) -> list[str] | None: 
        pass
    async def clear_by_profile(self, profile_name: str) -> list[str] | None: 
        pass
    async def keys(self) -> list[str] | None: 
        pass
    async def items(self) -> list[CacheEntry] | None: 
        pass
    async def metadata(self) -> list[CacheMetadata] | None: 
        pass
    async def key_metadata(self, key: str) -> CacheMetadata | None: 
        pass
    async def update_profile_settings(
        self,
        name: str,
        time_to_live: int,
        tags: list[str],
        ttl_cleanup_interval: int,
        memory_based_eviction: bool,
        free_memory_target: float,
        memory_cleanup_interval: int,
        max_items_in_memory: int
    ) -> None: 
        pass
    async def profile(self, name: str) -> Profile | None: 
        pass
    async def list_profiles(self) -> list[Profile] | None: 
        pass
    async def delete_profile(self, name: str) -> None: 
        pass
    async def log_access(
        self, 
        entry: AccessLogEntry, 
        batch: bool = True
    ) -> None: 
        pass
    async def log_access_batch(self, entries: list[AccessLogEntry]) -> None: 
        pass
    async def stats(self, limit: int = 10) -> list[AccessLogEntry] | None: 
        pass
    async def key_access_logs(self, key: str) -> AccessLogEntry | None: 
        pass
    async def access_logs(self) -> list[AccessLogEntry] | None: 
        pass
    async def delete_access_logs(self, key: str) -> None: 
        pass
    async def clear_access_logs(self) -> None: 
        pass
    async def log_eviction(
        self, 
        entry: EvictionLogEntry, 
        batch: bool = True
    ) -> None: 
        pass
    async def log_eviction_batch(self, entries: list[EvictionLogEntry]) -> None: 
        pass
    async def eviction_logs(
        self, 
        limit: int = 1000
    ) -> list[EvictionLogEntry] | None: 
        pass
    async def clear_eviction_logs(self) -> None: 
        pass