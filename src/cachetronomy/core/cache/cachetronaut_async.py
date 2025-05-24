import os
import asyncio
from concurrent.futures import ThreadPoolExecutor
from contextlib import suppress
from datetime import timedelta
from typing import Any, Awaitable

from pydantic import BaseModel

from cachetronomy.core.cache.cachetronomer import Cachetronomer
from cachetronomy.core.eviction.time_to_live import TTLEvictionThread
from cachetronomy.core.eviction.memory import MemoryEvictionThread
from cachetronomy.core.types.settings import CacheSettings
from cachetronomy.core.store.sqlite.asynchronous import AsyncSQLiteStore
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
    memory_key_count as _memory_key_count,
)
from cachetronomy.core.utils.time_utils import _now


class AsyncCachetronaut(Cachetronomer):
    def __init__(
        self, 
        *, 
        db_path: str | None = None, 
        profile: str | Profile | None = None
    ):
        settings = CacheSettings()
        self.db_path = db_path or settings.db_path
        self.store = AsyncSQLiteStore(self.db_path)
        self._bg_tasks: set[asyncio.Task] = set()
        self._workers = min(32, os.cpu_count() * 5)
        self._executor = ThreadPoolExecutor(max_workers=self._workers)
        default = Profile(name='default')
        self._current_profile = default
        self._init_profile_arg = profile
        super().__init__(
            store=self.store,
            max_items_in_memory=default.max_items_in_memory,
            default_time_to_live=default.time_to_live,
            default_tags=default.tags,
        )

    def _handle_eviction(
        self,
        key: str,
        *,
        reason: str | None,
        count: int | None,
        value: Any | None
    ) -> None:
        self._track(
            self._handle_eviction_async(key, reason, count, value)
        )

    async def _handle_eviction_async(
            self,
            key: str,
            reason: str | None,
            count: int | None,
            value: Any | None
        ):
            meta : CacheMetadata = await self.store.key_metadata(key)
            if meta and meta.expire_at <= _now():
                reason = 'time_eviction'
            if count is not None:
                count = count 
            else:
                count = self._memory.stats().get(key, 0)
            self._track(self.store.log_eviction(
                                            EvictionLogEntry(
                                                id=None,
                                                key=key,
                                                evicted_at=_now(),
                                                reason=reason,
                                                last_access_count=count,
                                                evicted_by_profile=self.profile.name,
                                            )
                        )
            )

    def _track(self, coro: Awaitable[Any]) -> None:
        task = asyncio.create_task(coro)
        self._bg_tasks.add(task)
        def _done_callback(fut):
            self._bg_tasks.discard(fut)
            try:
                exc = fut.exception()
            except asyncio.CancelledError:
                return
            if exc and not isinstance(exc, asyncio.CancelledError):
                print(f'Background task error: {exc!r}')
        task.add_done_callback(_done_callback)

    @property
    def profile(self) -> Profile:
        return self._current_profile

    def _apply_profile_settings(self, profile: Profile):
        self.time_to_live = profile.time_to_live
        self.ttl_cleanup_interval = profile.ttl_cleanup_interval
        self.memory_based_eviction = profile.memory_based_eviction
        self.free_memory_target = profile.free_memory_target
        self.memory_cleanup_interval = profile.memory_cleanup_interval
        self.max_items_in_memory = profile.max_items_in_memory
        self.tags = list(profile.tags)

    async def init_async(self):
        await self.store.init()
        await self.set_profile(self._init_profile_arg)
        register_callback(lambda key: self._track(
            self.store.log_access( 
                    AccessLogEntry(
                        key=key, 
                        access_count=_memory_key_count(key),
                        last_accessed=_now(),
                        last_accessed_by_profile=self.profile.name
                    )
                )
            )
        )
        self.ttl_eviction_thread = TTLEvictionThread(
            self, 
            asyncio.get_running_loop(), 
            self.ttl_cleanup_interval
        )
        self.ttl_eviction_thread.start()
        self.memory_eviction_thread = MemoryEvictionThread(
            self,
            asyncio.get_running_loop(),
            self.memory_cleanup_interval,
            self.free_memory_target
        )
        self.memory_eviction_thread.start()

    async def shutdown(self):
        if getattr(self, 'ttl_eviction_thread', None):
            self.ttl_eviction_thread.stop()
            self.ttl_eviction_thread.join()
        if getattr(self, 'memory_eviction_thread', None):
            self.memory_eviction_thread.stop()
            if self.memory_eviction_thread.is_alive():
                self.memory_eviction_thread.join()
        for task in list(self._bg_tasks):
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task
        self._executor.shutdown(wait=True)
        await self.store.close()

    async def get(
        self, 
        key: str, 
        model: BaseModel | None = None, 
        promote: bool = True
    ) -> CacheEntry:
        memory_data = self._memory.get(key)
        if memory_data is not None:
            return memory_data
        entry = await self.store.get(key)
        if not entry:
            return None
        if _now() > entry.expire_at:
            self._memory.evict(key)
            await self.store.delete(key)
            return None
        if promote:
            self._track(self.store.log_access( 
                    AccessLogEntry(
                        key=key, 
                        access_count=_memory_key_count(key),
                        last_accessed=_now(),
                        last_accessed_by_profile=self.profile.name
                    )
                )
            )
            promote_key(key)

        store_data = deserialize(entry.data, entry.fmt, model_type=model)
        self._memory.set(key, store_data)
        return store_data

    async def set(
        self,
        key: str,
        value: Any,
        time_to_live: int | None = None,
        version: int | None = None,
        tags: list[str] | None = None,
        prefer: str | None = None,
    ) -> None:
        ttl = time_to_live or self.time_to_live
        expire_at = _now() + timedelta(seconds=ttl)
        version = version or getattr(
            getattr(value, '__class__', None), '__cache_version__', 1
        )
        tags = tags or self.tags
        payload, fmt = serialize(value, prefer=prefer)

        self._memory.set(key, value)
        await self.store.set(CacheEntry(
             key=key, 
             data=payload, 
             fmt=fmt, 
             expire_at=expire_at, 
             tags=tags, 
             saved_by_profile=self.profile.name, 
             version=version
            )
        )

    async def delete(self, key: str) -> None:
        await self.store.delete(key)

    async def memory_keys(self) -> Awaitable[list[str]] | None:
        return self._memory.keys()
    
    async def store_keys(self) -> list[str] | None:
        return await self.store.keys()

    async def evict(self, key: str) -> None:
        self._memory.evict(key, reason='user_eviction')
        await self.store.delete(key)

    async def evict_all(self) -> None:
        memory_keys = list(await self.memory_keys())
        for key in memory_keys:
            self._memory.evict(key, reason='manual_eviction_clear_full_cache')

    async def clear_all(self) -> None:
        for key in await self.memory_keys():
            self._memory.evict(key, reason='manual_eviction_clear_full_cache')
        await self.store.clear_all()

    async def clear_by_tags(self, tags: list[str], exact_match: bool) -> None:
        invalidated_keys = await self.store.clear_by_tags(tags)
        for key in invalidated_keys:
            self._memory.evict(key, reason='tag_invalidation')

    async def clear_expired(self) -> list[ExpiredEntry] | None:
        for expired in await self.store.clear_expired():
            self._memory.evict(expired.key, reason='time_eviction')

    async def clear_by_profile(self, profile: str) -> None:
         await self.store.clear_by_profile(profile)

    async def items(self) -> list[CacheEntry] | None:
        return await self.store.items()

    async def memory_stats(self) -> list[tuple[str, int]] | None:
        return self._memory.stats()

    async def store_stats(
        self, 
        limit: int | None = 25
    ) -> list[AccessLogEntry] | None:
        await self.store.access_logger.flush()
        return await self.store.stats(limit)

    async def store_metadata(self) -> list[CacheMetadata] | None:
        return await self.store.metadata()

    async def key_metadata(self, key: str) -> CacheMetadata | None:
        return await self.store.key_metadata(key)

    # ——— Profiles Log API ———

    async def get_profile(self, name: str) -> Profile | None:
        return await self.store.profile(name)

    async def set_profile(self, prof: str | Profile | None):
        if prof is None:
            name = 'default'
        elif isinstance(prof, str):
            name = prof
        else:
            self._current_profile = prof
            await self.store.update_profile_settings(**prof.model_dump())
            self._apply_profile_settings(prof)
            return

        profile = await self.store.profile(name)
        if not profile:
            profile = Profile(name=name)
            await self.store.upsert_profile(**profile.model_dump())
        self._current_profile = profile
        self._apply_profile_settings(profile)

    async def list_profiles(self) -> list[Profile] | None:
        return await self.store.list_profiles()

    async def update_active_profile(self, **kwargs) -> None:
        new_profile = self.profile.model_copy(update=kwargs)
        await self.store.update_profile_settings(**new_profile.model_dump())
        self._apply_profile_settings(new_profile)

    async def delete_profile(self, name: str) -> None:
        await self.store.delete_profile(name)

    # ——— Access Log API ———

    async def key_access_logs(self, key: str) -> AccessLogEntry | None:
        await self.store.access_logger.flush()
        return await self.store.key_access_logs(key)

    async def access_logs(self) -> list[AccessLogEntry] | None:
        await self.store.access_logger.flush()
        return await self.store.access_logs()

    async def delete_access_logs(self, key: str) -> None:
       await self.store.delete_access_logs(key)

    async def clear_access_logs(self) -> None:
        await self.store.clear_access_logs()

    # ——— Eviction Log API ———

    async def eviction_logs(
        self, 
        limit: int
    ) -> list[EvictionLogEntry] | None:
        await self.store.eviction_logger.flush()
        return await self.store.eviction_logs(limit)

    async def clear_eviction_logs(self) -> None:
        await self.store.clear_eviction_logs()