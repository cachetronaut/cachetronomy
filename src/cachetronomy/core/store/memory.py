import asyncio
import logging
import threading

from collections import OrderedDict
from datetime import datetime
from typing import Any, Callable

from synchronaut import synchronaut

from cachetronomy.core.access_frequency import (
    memory_key_count,
    promote_key,
    deregister_key
)
from cachetronomy.core.utils.time_utils import _now

# Sentinel distinguishing "key absent" from a legitimately cached ``None``.
MISS = object()


class MemoryCache:
    def __init__(
        self,
        max_items: int | None,
        on_evict: Callable[..., Any] | None,
        loop: asyncio.AbstractEventLoop | None = None,
    ):
        self.max_items = max_items
        self._store = OrderedDict()
        self._expiry: dict[str, datetime] = {}
        self._lock = threading.RLock()
        self._on_evict = on_evict
        self._loop = loop

    @synchronaut()
    async def get(self, key: str) -> Any:
        '''Return the cached value, or ``MISS`` if absent/expired.'''
        expired_value: Any = MISS
        with self._lock:
            if key not in self._store:
                return MISS
            expire_at = self._expiry.get(key)
            if expire_at is not None and _now() > expire_at:
                expired_value = self._store.pop(key)
                self._expiry.pop(key, None)
            else:
                value = self._store.pop(key)
                self._store[key] = value  # move to MRU end
                promote_key(key)
                return value
        # Expired: drop bookkeeping and best-effort log, then report a miss.
        self._finalize_eviction(key, expired_value, reason='time_eviction')
        return MISS

    def set(self, key: str, value: Any, expire_at: datetime | None = None) -> None:
        evicted: tuple[str, Any] | None = None
        with self._lock:
            self._store.pop(key, None)
            self._store[key] = value
            if expire_at is not None:
                self._expiry[key] = expire_at
            else:
                self._expiry.pop(key, None)
            if isinstance(self.max_items, int) and len(self._store) > self.max_items:
                # Evict the least-frequently-used existing entry, never the one
                # we just inserted.
                candidates = [k for k in self._store if k != key]
                if candidates:
                    ev_key = min(candidates, key=memory_key_count)
                    evicted = (ev_key, self._store.pop(ev_key, None))
                    self._expiry.pop(ev_key, None)
        if evicted is not None:
            ev_key, ev_value = evicted
            self._finalize_eviction(ev_key, ev_value, reason='memory_eviction')

    def _pop(self, key: str) -> Any:
        '''Remove a key from the in-memory store, returning its value or ``MISS``.'''
        with self._lock:
            self._expiry.pop(key, None)
            return self._store.pop(key, MISS)

    def _finalize_eviction(self, key: str, value: Any, reason: str) -> None:
        '''Update access bookkeeping and fire the (async) eviction callback.

        Safe to call from any thread, including the event loop thread: the
        callback is scheduled without blocking so it never deadlocks the loop.
        '''
        count = memory_key_count(key)
        deregister_key(key)
        if not self._on_evict:
            return
        loop = self._loop
        if loop is not None and loop.is_running():
            # Common case under synchronaut: a background loop is running, so
            # hand the async eviction-log write off to it without blocking.
            try:
                asyncio.run_coroutine_threadsafe(
                    self._on_evict(key=key, value=value, count=count, reason=reason),
                    loop,
                )
            except Exception:
                logging.debug('eviction-log dispatch failed', exc_info=True)
        # If no loop is running we are in a purely synchronous context with no
        # safe place to await the async eviction-log callback. The in-memory
        # eviction itself is already done; skip the (best-effort) log rather
        # than leak an un-awaited coroutine.

    async def evict(self, key: str, reason: str = 'memory_eviction') -> None:
        value = self._pop(key)
        if value is MISS:
            return
        count = memory_key_count(key)
        if self._on_evict:
            await self._on_evict(
                key=key, value=value, count=count, reason=reason
            )
        deregister_key(key)

    def clear(self) -> None:
        with self._lock:
            items = list(self._store.items())
            self._store.clear()
            self._expiry.clear()
        for key, value in items:
            self._finalize_eviction(key, value, reason='memory_eviction')

    def stats(self) -> list[tuple[str, int]]:
        with self._lock:
            result = [(k, memory_key_count(k)) for k in self._store]
        result.sort(key=lambda kv: kv[1], reverse=True)
        return result

    def keys(self) -> list[str]:
        with self._lock:
            return list(self._store.keys())
