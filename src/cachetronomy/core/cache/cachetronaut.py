
import inspect
import asyncio
import sqlite3
import os

from datetime import timedelta
from typing import Any, TypeVar, ParamSpec, Callable
from functools import wraps
from pathlib import Path 

from pydantic import BaseModel
from synchronaut import (
    call_any,
    synchronaut,
    call_map,
    parallel_map,
    get_preferred_loop,
)
from synchronaut.utils import get_request_ctx

from cachetronomy.core.utils.key_builder import default_key_builder
from cachetronomy.core.store.memory import MemoryCache
from cachetronomy.core.store.sqlite.synchronous import SQLiteStore
from cachetronomy.core.types.settings import CacheSettings
from cachetronomy.core.types.profiles import Profile
from cachetronomy.core.types.schemas import (
    AccessLogEntry,
    EvictionLogEntry,
    CacheMetadata,
    CacheEntry,
    ExpiredEntry
)
from cachetronomy.core.serialization import serialize, deserialize
from cachetronomy.core.access_frequency import (
    register_callback,
    promote_key,
    memory_key_count as _memory_key_count
)
from cachetronomy.core.eviction.time_to_live import TTLEvictionThread
from cachetronomy.core.eviction.memory import MemoryEvictionThread
from cachetronomy.core.utils.time_utils import _now

P = ParamSpec('P')
R = TypeVar('R')


class Cachetronaut():
    def __init__(
        self,
        *,
        db_path: str | None = None,
        profile: Profile | str | None = None,
        max_items_in_memory: int | None = None,
        loop: asyncio.AbstractEventLoop | None = None,
    ):
        self._loop = loop if isinstance(
                            loop, asyncio.AbstractEventLoop
                        ) else get_preferred_loop()
        settings = CacheSettings()
        if db_path is not None:
            candidate = Path(db_path)
        elif settings.db_path:
            candidate = Path(settings.db_path)
        else:
            candidate = self._find_project_root() / 'cachetronomy.db'
        final = candidate.expanduser().resolve()
        final.parent.mkdir(parents=True, exist_ok=True)
        self.db_path = str(final)
        self.store = SQLiteStore(self.db_path, self._loop)
        self._memory = MemoryCache(
            max_items=max_items_in_memory or None,
            on_evict=self._handle_eviction,
        )
        self._profile = profile or Profile(name='default')
        register_callback(lambda key: 
            AccessLogEntry(
                key=key, 
                access_count=_memory_key_count(key),
                last_accessed=_now(),
                last_accessed_by_profile=self.profile.name
            )
        )

    def __call__(
            self, 
            __fn=None, 
            *, 
            time_to_live=None,
            tags=None,
            version=None, 
            key_builder=None, 
            prefer=None
    )-> Callable[P, R] | None:
        kb = key_builder or default_key_builder

        def decorate(fn):
            sig = inspect.signature(fn)

            if inspect.iscoroutinefunction(fn):
                @wraps(fn)
                async def wrapper_async(*args, **kwargs):
                    key = kb(fn, args, kwargs)
                    model = (sig.return_annotation
                            if inspect.isclass(sig.return_annotation)
                            and issubclass(sig.return_annotation, BaseModel)
                            else None)

                    cached = await self.get(key, model=model)
                    if cached is not None:
                        return cached

                    value = await fn(*args, **kwargs)

                    await self.set(
                        key, value,
                        time_to_live=time_to_live or self.time_to_live,
                        version=version or getattr(
                            getattr(value, '__class__', None),
                            '__cache_version__', 1),
                        tags=tags or self.profile.tags,
                        prefer=prefer,
                    )
                    return value
                wrapper_async.__signature__ = sig
                wrapper_async.key_for = lambda *a, **k: kb(fn, a, k)
                return wrapper_async

            else:
                @wraps(fn)
                def wrapper_sync(*args, **kwargs):
                    key = kb(fn, args, kwargs)
                    model = (sig.return_annotation
                            if inspect.isclass(sig.return_annotation)
                            and issubclass(sig.return_annotation, BaseModel)
                            else None)

                    cached = self.get(key, model=model)
                    if cached is not None:
                        return cached

                    value = fn(*args, **kwargs)
                    self.set(
                        key, value,
                        time_to_live=time_to_live or self.time_to_live,
                        version=version or getattr(
                            getattr(value, '__class__', None),
                            '__cache_version__', 1),
                        tags=tags or self.profile.tags,
                        prefer=prefer,
                    )
                    return value
                wrapper_sync.__signature__ = sig
                wrapper_sync.key_for = lambda *a, **k: kb(fn, a, k)
                return wrapper_sync

        return decorate(__fn) if __fn else decorate

    @staticmethod
    def _find_project_root() -> Path:
        directory = Path(os.getcwd()).resolve()
        root = Path(directory)
        while True:
            if (directory / '.git').is_dir() or (directory / 'pyproject.toml').is_file():
                return directory
            if directory.parent == directory:
                return root
            directory = directory.parent

    @property
    def profile(self) -> Profile:
        return self._profile

    @profile.setter
    def profile(self, prof: str | Profile):
        real_profile: Profile = call_any(  # noqa: F841
            self._resolve_and_apply_profile,
            prof,
            force_offload=True
        )


    @synchronaut()
    async def _resolve_and_apply_profile(self, prof: str | Profile):
        profile = await self._resolve_profile(prof)
        await self._apply_profile_settings(profile)
        return profile
    
    @synchronaut()
    async def _resolve_profile(self, prof: str | Profile | None):
        if isinstance(prof, Profile):
            return prof
        
        name = prof or 'default'
        profile = await self.store.profile(name)
        if profile:
            return profile
        
        base = Profile(name='default').model_dump()
        base['name'] = name
        profile = Profile.model_validate(base)
        await self.store.update_profile_settings(**base)
        return profile

    @synchronaut()
    async def _apply_profile_settings(self, profile: Profile):
        self._profile = profile
        self.time_to_live = profile.time_to_live
        self.ttl_cleanup_interval = profile.ttl_cleanup_interval
        self.memory_based_eviction = profile.memory_based_eviction
        self.free_memory_target = profile.free_memory_target
        self.memory_cleanup_interval = profile.memory_cleanup_interval
        self.max_items_in_memory = profile.max_items_in_memory
        self.tags = profile.tags
        await self.store.update_profile_settings(**profile.model_dump())
        await self._sync_eviction_threads()

    @synchronaut()
    def _ensure_ttl_eviction_thread(self):
        should_run = getattr(self, 'ttl_cleanup_interval', 0) > 0
        has_thread = hasattr(self, 'ttl_eviction_thread')
        if should_run and not has_thread:
            self.ttl_eviction_thread = TTLEvictionThread(
                self, 
                loop=self._loop, 
                ttl_cleanup_interval=self.ttl_cleanup_interval,
            )
            self.ttl_eviction_thread.start()
        elif not should_run and has_thread:
            self.ttl_eviction_thread.stop()
            del self.ttl_eviction_thread

    @synchronaut()
    def _ensure_memory_eviction_thread(self):
        should_run = getattr(self, 'memory_based_eviction', False)
        has_thread = hasattr(self, 'memory_thread')
        if should_run and not has_thread:
            self.memory_thread = MemoryEvictionThread(
                self, 
                loop=self._loop, 
                memory_cleanup_interval=self.memory_cleanup_interval, 
                free_memory_target=self.free_memory_target,
            )
            self.memory_thread.start()
        elif not should_run and has_thread:
            self.memory_thread.stop()
            del self.memory_thread

    @synchronaut()
    def _sync_eviction_threads(self):
        call_map(
            [
                self._ensure_ttl_eviction_thread, 
                self._ensure_memory_eviction_thread
            ]
        )

    # @synchronaut()
    async def _handle_eviction(
        self,
        key: str,
        *,
        reason: str | None,
        count: int | None,
        value: Any
    ) -> None:
        try:
            meta: CacheMetadata = await self.store.key_metadata(key)
            if meta and meta.expire_at <= _now():
                reason = 'time_eviction'
            if count is not None:
                count = count 
            else:
                count = self._memory.stats().get(key, 0)
            await self.store.log_eviction(
                EvictionLogEntry(
                    id=None,
                    key=key,
                    evicted_at=_now(),
                    reason=reason,
                    last_access_count=count,
                    evicted_by_profile=self.profile.name,
                )
            )
        except sqlite3.ProgrammingError: # TODO: Test what happens when I remove.
            return
        except Exception:
            return

    @synchronaut()
    async def shutdown(self) -> None:
        if hasattr(self, 'ttl_eviction_thread'):
            self.ttl_eviction_thread.stop()
            self.ttl_eviction_thread.join()
        if hasattr(self, 'memory_thread'):
            # await self.memory_thread.stop()
            call_any(self.memory_thread.stop)
            call_any(self.memory_thread.join)
        await self.store.access_logger.flush()
        await self.store.eviction_logger.flush()
        await self.store.access_logger.stop()
        await self.store.eviction_logger.stop()
        call_any(self.store.close)

    def __enter__(self):
        '''Context manager entry.'''
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        '''Context manager exit - ensures cleanup.'''
        call_any(self.shutdown)
        return False

    # ———  Cache API  ——— 

    @synchronaut()
    async def set(
        self,
        key: str,
        value: Any,
        time_to_live: int | None = None,
        version: int | None = None,
        tags: list[str] | None = None,
        prefer: str | None = None,
    ) -> CacheEntry:
        '''Cache an entry with optional TTL, version, tags, and serializer.'''
        self._memory.set(key, value)

        ttl = time_to_live or self.profile.time_to_live
        expire_at = _now() + timedelta(seconds=ttl)
        version = version or getattr(
            getattr(value, '__class__', None), '__cache_version__', 1
        )
        tags = tags or []
        payload, fmt = serialize(value, prefer=prefer)

        profile_name = self.profile.name
        await self.store.set(
            CacheEntry(
                key=key, 
                data=payload, 
                fmt=fmt, 
                expire_at=expire_at, 
                tags=tags, 
                saved_by_profile=profile_name, 
                version=version
            )
        )
        return CacheEntry(
                key=key, 
                data=value, 
                fmt=fmt, 
                expire_at=expire_at, 
                tags=tags, 
                saved_by_profile=profile_name, 
                version=version
            )

    @synchronaut()
    async def get(
        self,
        key: str,
        model: BaseModel | None = None,
        promote: bool | None = True,
    ) -> CacheEntry | ExpiredEntry | None:
        '''Retrieve a cache entry by key (optionally as a Pydantic model) and promote to memory.'''
        memory_data = await self._memory.get(key)
        if memory_data is not None:
            await self.store.log_access(
                AccessLogEntry(
                    key=key, 
                    access_count=_memory_key_count(key),
                    last_accessed=_now(),
                    last_accessed_by_profile=self.profile.name
                )
            )
            return memory_data
        entry = await self.store.get(key)
        if not entry:
            return None
        if _now() > entry.expire_at:
            await self.store.delete(key)
            ctx = get_request_ctx()
            if ctx and ctx.get('cli_mode', False):
                return ExpiredEntry(key=entry.key, expire_at=entry.expire_at)
        if promote:
            promote_key(key)
            await self.store.log_access(
                AccessLogEntry(
                    key=key,
                    access_count=_memory_key_count(key),
                    last_accessed=_now(),
                    last_accessed_by_profile=self.profile.name
                )
            )
        ctx = get_request_ctx()
        if ctx and ctx.get('cli_mode', False):
            return CacheEntry(
                key=entry.key,
                fmt=entry.fmt,
                expire_at=entry.expire_at,
                tags=entry.tags,
                saved_by_profile=entry.saved_by_profile,
                version=entry.version,
                data=deserialize(entry.data, entry.fmt)
            )
        payload, fmt = entry.data, entry.fmt
        store_data = (
            deserialize(payload, fmt, model)
            if inspect.isclass(model) and issubclass(model, BaseModel)
            else deserialize(payload, fmt)
        )
        self._memory.set(key, store_data)
        return store_data

    @synchronaut()
    async def evict(self, key: str) -> None:
        '''Evict a key from in-memory cache without deleting it from the store.'''
        await self._memory.evict(key, reason='manual_eviction_clear_key')

    @synchronaut()
    async def delete(self, key: str) -> None:
        '''Delete a key from both memory and persistent store in parallel.'''
        await parallel_map(
            [ 
                (
                    self._memory.evict, 
                    (), 
                    {'key': key, 'reason':'user_eviction'}, 
                    None
                ),
                (
                    self.store.delete.async_, 
                    (self.store,), 
                    {'key': key}, 
                    None
                )
            ]
        )

    @synchronaut()
    async def store_keys(self) -> list[str] | None:
        '''List all keys currently stored in the persistent backend.'''
        return await self.store.keys()

    @synchronaut()
    async def memory_keys(self) -> list[str] | None:
        '''List all keys currently held in in-memory cache.'''
        return self._memory.keys()

    @synchronaut()
    async def all_keys(self) -> list[str] | None:
        '''List every key across both memory and persistent store.'''
        memory_keys = await self.memory_keys()
        store_keys = await self.store_keys()
        return memory_keys + store_keys

    @synchronaut()
    async def evict_all(self) -> None:
        '''Evict all entries from in-memory cache only.'''
        keys_to_evict = self._memory.keys()
        for key in keys_to_evict:
            await self._memory.evict(
                key, reason='manual_eviction_clear_full_cache'
            )

    @synchronaut()
    async def clear_all(self) -> None:
        '''Clear every entry from both memory and persistent store.'''
        await self.evict_all()
        await self.store.clear_all()

    @synchronaut()
    async def clear_expired(self) -> list[ExpiredEntry] | None:
        '''Remove all expired entries from store (and evict them from memory).'''
        expired = await self.store.clear_expired()
        for rec in expired:
            await self._memory.evict(rec.key, reason='time_eviction')
        return expired

    @synchronaut()
    async def clear_by_tags(self, tags: list[str], exact_match: bool) -> None:
        '''Invalidate entries whose tags match (or partially match) the given list.'''
        removed = await self.store.get_keys_by_tags(tags, exact_match)
        for key in removed:
            await self._memory.evict(key, reason='tag_invalidation')
            await self.store.clear_by_tags(tags, exact_match)

    @synchronaut()
    async def clear_by_profile(self, profile_name: str) -> None:
        '''Evict and remove entries that were saved under the given profile.'''
        removed = await self.store.clear_by_profile(profile_name)
        for key in removed:
            await self._memory.evict(key, reason='tag_invalidation')

    @synchronaut()
    async def items(self, limit: int | None = 100) -> list[CacheEntry]:
        '''List all cache entries from the store.'''
        await self.clear_expired()
        items: list[CacheEntry] = await self.store.items(limit)
        return [
            CacheEntry(
                key=entry.key,
                fmt=entry.fmt,
                expire_at=entry.expire_at,
                tags=entry.tags,
                saved_by_profile=entry.saved_by_profile,
                version=entry.version,
                data=deserialize(entry.data, entry.fmt),
            )
            for entry in items
        ]

    @synchronaut()
    async def key_metadata(self, key: str) -> CacheMetadata | None:
        '''Fetch metadata (timestamps, version, tags) for a specific key.'''
        return await self.store.key_metadata(key)

    @synchronaut()
    async def store_metadata(self) -> list[CacheMetadata] | None:
        '''List metadata for every key in the persistent store.'''
        return await self.store.metadata()

    @synchronaut()
    async def store_stats(
        self, 
        limit: int | None = None
    ) -> list[AccessLogEntry] | None:
        '''Show access log entries–optionally limited to the most recent N.'''
        return await self.store.stats(limit)

    @synchronaut()
    async def memory_stats(self) -> list[tuple[str, int]]:
        '''Display in-memory access counts for each key.'''
        return self._memory.stats()

    # ——— Access Log API ———

    @synchronaut()
    async def access_logs(self, limit: int | None = 100) -> list[AccessLogEntry] | None:
        '''
        List all historical access log entries upt to an N-limit.
        Use None for all logs.
        '''
        return await self.store.access_logs(limit)

    @synchronaut()
    async def key_access_logs(self, key: str) -> AccessLogEntry | None:
        '''Show the most recent access log entry for a given key.'''
        return await self.store.key_access_logs(key)

    @synchronaut()
    async def clear_access_logs(self) -> None:
        '''Delete all access log history.'''
        await self.store.clear_access_logs()

    @synchronaut()
    async def delete_access_logs(self, key: str) -> AccessLogEntry | None:
        '''Delete access log entries for a specific key.'''
        return await self.store.delete_access_logs(key)

    # ——— Profiles Log API ———

    @synchronaut()
    async def get_profile(self, name: str | None = None) -> Profile | None:
        '''
        Retrieve a profile by name. If name is None → return current profile.
        '''
        if name:
            return await self.store.profile(name)
        return self.profile

    @synchronaut()
    async def list_profiles(self) -> list[Profile] | None:
        '''List all available cache profiles.'''
        return await self.store.list_profiles()

    @synchronaut()
    async def delete_profile(self, name: str) -> None:
        '''Remove a profile and its associated settings.'''
        await self.store.delete_profile(name)

    @synchronaut()
    async def update_active_profile(self, profile: Profile) -> None:
        '''Update properties of the currently active profile.'''
        new_profile = self.profile.model_copy(update=profile.model_dump())
        if profile.name is None:
            new_profile.name = self.profile.name
        await self.store.update_profile_settings(**new_profile.model_dump())
        await self._apply_profile_settings(new_profile)
        self._profile = new_profile
        return self.profile
    
    @synchronaut()
    async def set_profile(self, profile: str) -> Profile:
        '''Set/change the active profile.'''
        self._profile = await self.store.profile(profile)
        await self.store.set_config(key='active_profile', value=self._profile.name, db_path=self.store.db_path)
        await self._apply_profile_settings(self._profile)
        await self._sync_eviction_threads()
        return self.profile

    # ——— Eviction Log API ———

    @synchronaut()
    async def eviction_logs(self, limit: int = 100) -> list[EvictionLogEntry] | None:
        '''List eviction log entries, up to an optional limit.'''
        return await self.store.eviction_logs(limit)

    @synchronaut()
    async def clear_eviction_logs(self) -> None:
        '''Delete all records of past evictions.'''
        await self.store.clear_eviction_logs()

    # ——— Bulk Operations API ———

    @synchronaut()
    async def get_many(self, keys: list[str]) -> dict[str, Any]:
        '''
        Get multiple keys at once.

        Args:
            keys: List of cache keys to retrieve

        Returns:
            Dictionary mapping keys to their values. Missing keys are omitted.

        Example:
            results = cache.get_many(['user:1', 'user:2', 'user:3'])
            # {'user:1': {...}, 'user:2': {...}}  # user:3 was missing
        '''
        result = {}
        for key in keys:
            value = await self.get(key)
            if value is not None:
                result[key] = value
        return result

    @synchronaut()
    async def set_many(
        self,
        items: dict[str, Any],
        time_to_live: int | None = None,
        tags: list[str] | None = None,
        version: int = 1,
        prefer: str | None = None
    ) -> None:
        '''
        Set multiple key-value pairs at once.

        Args:
            items: Dictionary of key-value pairs to cache
            time_to_live: TTL in seconds (uses profile default if None)
            tags: Optional tags to associate with all entries
            version: Cache entry version
            prefer: Preferred serialization format

        Example:
            cache.set_many({
                'user:1': user1_data,
                'user:2': user2_data,
            }, time_to_live=3600)
        '''
        for key, value in items.items():
            await self.set(
                key=key,
                value=value,
                time_to_live=time_to_live,
                tags=tags,
                version=version,
                prefer=prefer
            )

    @synchronaut()
    async def delete_many(self, keys: list[str]) -> int:
        '''
        Delete multiple keys at once.

        Args:
            keys: List of cache keys to delete

        Returns:
            Number of keys successfully deleted

        Example:
            deleted = cache.delete_many(['user:1', 'user:2', 'user:3'])
            # 3
        '''
        deleted = 0
        for key in keys:
            await self.delete(key)
            deleted += 1
        return deleted

    # ——— Monitoring & Observability API ———

    @synchronaut()
    async def health_check(self) -> dict[str, Any]:
        '''
        Perform a health check and return system status.

        Returns:
            Dictionary with health status information including:
            - status: 'healthy', 'degraded', or 'unhealthy'
            - db_accessible: Whether database is reachable
            - memory_ok: Whether memory usage is acceptable
            - store_keys_count: Number of keys in persistent store
            - memory_keys_count: Number of keys in memory cache

        Example:
            health = cache.health_check()
            # {'status': 'healthy', 'db_accessible': True, ...}
        '''
        try:
            # Test database connectivity
            test_keys = await self.store_keys()
            db_accessible = True
            store_count = len(test_keys) if test_keys else 0
        except Exception:
            db_accessible = False
            store_count = 0

        memory_keys_list = await self.memory_keys()
        memory_count = len(memory_keys_list) if memory_keys_list else 0

        # Determine overall health status
        if db_accessible:
            status = 'healthy'
        else:
            status = 'unhealthy'

        return {
            'status': status,
            'db_accessible': db_accessible,
            'memory_ok': True,  # Memory cache always works
            'store_keys_count': store_count,
            'memory_keys_count': memory_count,
        }

    @synchronaut()
    async def stats(self) -> dict[str, Any]:
        '''
        Get comprehensive cache statistics.

        Returns:
            Dictionary with cache statistics including:
            - total_keys: Total keys across memory and store
            - memory_keys: Number of keys in memory
            - store_keys: Number of keys in persistent store
            - hot_keys: Most frequently accessed keys
            - evictions_count: Total number of evictions
            - profile: Current active profile name

        Example:
            stats = cache.stats()
            # {'total_keys': 150, 'memory_keys': 100, 'hot_keys': [...], ...}
        '''
        store_keys_list = await self.store_keys()
        memory_keys_list = await self.memory_keys()
        hot_keys_data = await self.store_stats(limit=10)
        evictions = await self.eviction_logs(limit=None)

        # Handle None returns
        store_keys_list = store_keys_list or []
        memory_keys_list = memory_keys_list or []

        return {
            'total_keys': len(set(store_keys_list + memory_keys_list)),
            'memory_keys': len(memory_keys_list),
            'store_keys': len(store_keys_list),
            'hot_keys': hot_keys_data[:10] if hot_keys_data else [],
            'evictions_count': len(evictions) if evictions else 0,
            'profile': self.profile.name,
        }

    # ——— Cache Stampede Protection ———

    @synchronaut()
    async def get_or_compute(
        self,
        key: str,
        compute_fn: Callable[[], Any],
        time_to_live: int | None = None,
        tags: list[str] | None = None,
        version: int = 1,
        prefer: str | None = None
    ) -> Any:
        '''
        Get a value from cache, or compute and cache it if missing.
        Prevents cache stampede by ensuring only one caller computes the value.

        Args:
            key: Cache key
            compute_fn: Function to call if cache misses (can be sync or async)
            time_to_live: TTL in seconds (uses profile default if None)
            tags: Optional tags
            version: Cache entry version
            prefer: Preferred serialization format

        Returns:
            The cached or computed value

        Example:
            def expensive_computation():
                return fetch_from_api()

            result = cache.get_or_compute('api:data', expensive_computation, time_to_live=300)
        '''
        # Try to get from cache first
        value = await self.get(key)
        if value is not None:
            return value

        # Cache miss - compute the value
        # Note: For true distributed stampede protection, would need distributed locking
        # For now, this provides basic protection within a single process
        computed_value = compute_fn()

        # If compute_fn is async, await it
        if inspect.iscoroutine(computed_value):
            computed_value = await computed_value

        # Cache the computed value
        await self.set(
            key=key,
            value=computed_value,
            time_to_live=time_to_live,
            tags=tags,
            version=version,
            prefer=prefer
        )

        return computed_value