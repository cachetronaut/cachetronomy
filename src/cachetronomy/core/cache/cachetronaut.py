
import inspect
from datetime import timedelta
from typing import Any, TypeVar, ParamSpec
from collections import OrderedDict

from pydantic import BaseModel

from cachetronomy.core.cache.cachetronomer import Cachetronomer
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


class Cachetronaut(Cachetronomer):
    def __init__(
        self,
        *,
        db_path: str | None = None,
        profile: Profile | str | None = None,
    ):
        settings = CacheSettings()
        db_path = db_path or settings.db_path
        self.store = SQLiteStore(db_path)
        register_callback(lambda key: 
            AccessLogEntry(
                key=key, 
                access_count=_memory_key_count(key),
                last_accessed=_now(),
                last_accessed_by_profile=self.profile.name
            )
        )
        self._apply_profile_settings(profile)
        super().__init__(
            store=self.store,
            max_items_in_memory=self.max_items_in_memory,
            default_time_to_live=self.time_to_live,
            default_tags=self.tags,
        )
        self._sync_eviction_threads()

    @property
    def profile(self) -> Profile:
        return self._current_profile

    @profile.setter
    def profile(self, prof: str | Profile):
        if isinstance(prof, str):
            p = self.store.profile(prof)
            if p is None:
                temp = self._current_profile.model_copy(update={'name': prof})
                p = temp
        else:
            p = prof
        self.store.update_profile_settings(**p.model_dump())
        self._apply_profile_settings(p)
        self._sync_eviction_threads()

    def _apply_profile_settings(self, prof: str | Profile | None):
        if isinstance(prof, Profile):
            p = prof
        else:
            name = prof if isinstance(prof, str) else 'default'
            p = self.store.profile(name)
            if p is None:
                base = Profile(name='default').model_dump()
                base['name'] = name
                p = Profile.model_validate(base)
                self.store.update_profile_settings(**base)
        self._current_profile = p
        self.time_to_live = p.time_to_live
        self.ttl_cleanup_interval = p.ttl_cleanup_interval
        self.memory_based_eviction = p.memory_based_eviction
        self.free_memory_target = p.free_memory_target
        self.memory_cleanup_interval = p.memory_cleanup_interval
        self.max_items_in_memory = p.max_items_in_memory
        self.tags = p.tags

    def _ensure_ttl_eviction_thread(self):
        should_run = getattr(self, 'ttl_cleanup_interval', 0) > 0
        has_thread = hasattr(self, 'ttl_eviction_thread')
        if should_run and not has_thread:
            self.ttl_eviction_thread = TTLEvictionThread(
                self, loop=None, ttl_cleanup_interval=self.ttl_cleanup_interval,
            )
            self.ttl_eviction_thread.start()
        elif not should_run and has_thread:
            self.ttl_eviction_thread.stop()
            del self.ttl_eviction_thread

    def _ensure_memory_eviction_thread(self):
        should_run = getattr(self, 'memory_based_eviction', False)
        has_thread = hasattr(self, 'memory_thread')
        if should_run and not has_thread:
            self.memory_thread = MemoryEvictionThread(
                self, 
                loop=None, 
                memory_cleanup_interval=self.memory_cleanup_interval, 
                free_memory_target=self.free_memory_target,
            )
            self.memory_thread.start()
        elif not should_run and has_thread:
            self.memory_thread.stop()
            del self.memory_thread

    def _sync_eviction_threads(self):
        self._ensure_ttl_eviction_thread()
        self._ensure_memory_eviction_thread()

    def _handle_eviction(
        self,
        key: str,
        *,
        reason: str | None,
        count: int | None,
        value: Any
    ) -> None:
        meta: CacheMetadata =  self.store.key_metadata(key)
        if meta and meta.expire_at <= _now():
            reason = 'time_eviction'
        if count is not None:
            count = count 
        else:
            count = self._memory.stats().get(key, 0)
        self.store.log_eviction(
            EvictionLogEntry(
                id=None,
                key=key,
                evicted_at=_now(),
                reason=reason,
                last_access_count=count,
                evicted_by_profile=self.profile.name,
            )
        )

    def shutdown(self) -> None:
        if hasattr(self, 'ttl_eviction_thread'):
            self.ttl_eviction_thread.stop()
            self.ttl_eviction_thread.join()
        if hasattr(self, 'memory_thread'):
            self.memory_thread.stop()
            self.memory_thread.join()
        self.store.close()

    # ———  Cache API  ——— 
    def set(
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
        self.store.set(CacheEntry(
             key=key, 
             data=payload, 
             fmt=fmt, 
             expire_at=expire_at, 
             tags=tags, 
             saved_by_profile=self.profile.name, 
             version=version
            )
        )

    def get(
        self,
        key: str,
        model: BaseModel | None = None,
        promote: bool = True,
    ) -> CacheEntry:
        memory_data = self._memory.get(key)
        if memory_data is not None:
            return memory_data
        entry = self.store.get(key)
        if not entry:
            return None
        if _now() > entry.expire_at:
            self.store.delete(key)
            return None
        if promote:
            self.store.log_access(
                AccessLogEntry(
                    key=key, 
                    access_count=_memory_key_count(key),
                    last_accessed=_now(),
                    last_accessed_by_profile=self.profile.name
                )
            )
            promote_key(key)
        payload, fmt = entry.data, entry.fmt
        store_data = (
            deserialize(payload, fmt, model)
            if inspect.isclass(model) and issubclass(model, BaseModel)
            else deserialize(payload, fmt)
        )
        self._memory.set(key, store_data)
        return store_data

    def evict(self, key: str) -> None:
        self._memory.evict(key, reason='manual_eviction_clear_key')

    def delete(self, key: str) -> None:
        self._memory.evict(key, reason='user_eviction')
        self.store.delete(key)

    def store_keys(self) -> list[str] | None:
        return self.store.keys()

    def memory_keys(self) -> list[str] | None:
        return self._memory.keys()
    
    def all_keys(self) -> list[str] | None:
        return self.memory_keys() + self.store_keys()

    def evict_all(self) -> None:
        keys_to_evict = list(self._memory.keys())
        for key in keys_to_evict:
            self._memory.evict(key, reason='manual_eviction_clear_full_cache')

    def clear_all(self) -> None:
        self.evict_all()
        self.store.clear_all()

    def clear_expired(self) -> list[ExpiredEntry] | None:
        expired = self.store.clear_expired()
        for rec in expired:
            self._memory.evict(rec.key, reason='time_eviction')

    def clear_by_tags(
        self,
        tags: list[str],
        exact_match: bool = False
    ) -> None:
        removed = self.store.clear_by_tags(tags, exact_match)
        for key in removed:
            self._memory.evict(key, reason='tag_invalidation')

    def clear_by_profile(self, profile_name: str) -> None:
        removed = self.store.clear_by_profile(profile_name)
        for key in removed:
            self._memory.evict(key, reason='tag_invalidation')

    def items(self) -> list[CacheEntry] | None:
        return self.store.items()
    
    def store_metadata(self) -> list[CacheMetadata] | None:
        return self.store.metadata()

    def store_stats(self, limit: int | None = None) -> list[AccessLogEntry] | None:
        self.store.access_logger.flush()
        return self.store.stats(limit)

    def memory_stats(self) -> OrderedDict:
        return OrderedDict(self._memory.stats())

    # ——— Access Log API ———

    def access_logs(self) -> list[AccessLogEntry] | None:
        self.store.access_logger.flush()
        return self.store.access_logs()

    def key_access_logs(self, key: str) -> AccessLogEntry | None:
        self.store.access_logger.flush()
        return self.store.key_access_logs(key)

    def clear_access_logs(self) -> None:
        self.store.clear_access_logs()

    def delete_access_logs(self, key: str) -> AccessLogEntry | None:
        return self.store.delete_access_logs(key)

    # ——— Profiles Log API ———

    def get_profile(self, name: str) -> Profile | None:
        return self.store.profile(name)

    def list_profiles(self) -> list[Profile] | None:
        return self.store.list_profiles()

    def delete_profile(self, name: str) -> None:
        self.store.delete_profile(name)

    async def update_active_profile(self, **kwargs) -> None:
        new_profile = self.profile.model_copy(update=kwargs)
        self.store.update_profile_settings(**new_profile.model_dump())
        self._apply_profile_settings(new_profile)

    # ——— Eviction Log API ———

    def eviction_logs(self, limit: int = 1000) -> list[EvictionLogEntry] | None:
        self.store.eviction_logger.flush()
        return self.store.eviction_logs(limit)

    def clear_eviction_logs(self) -> None:
        self.store.clear_eviction_logs()

    