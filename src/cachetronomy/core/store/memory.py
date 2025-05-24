import threading
from collections import OrderedDict
from typing import Any, Callable
from cachetronomy.core.access_frequency import (
    memory_key_count, 
    promote_key, 
    deregister_key
)

class MemoryCache:
    def __init__(self, max_items: int, on_evict: Callable[..., None] | None):
        self.max_items = max_items
        self._store = OrderedDict()
        self._lock = threading.RLock()
        self._on_evict = on_evict

    def get(self, key: str) -> Any | None:
        with self._lock:
            value = self._store.get(key, None)
            if value is None: 
                return None
            self._store.pop(key)
            self._store[key] = value
            promote_key(key)
            return value

    def set(self, key: str, value: Any) -> None:
        with self._lock:
            self._store.pop(key, None)
            self._store[key] = value
            if isinstance(self.max_items, int) and len(self._store) > self.max_items:
                ev_key = min(self._store, key=lambda k: memory_key_count(k))
                self.evict(ev_key)

    def evict(self, key: str, reason: str = 'memory_eviction') -> None:
        with self._lock:
            value = self._store.pop(key, None)
            if value is None: 
                return
            count = memory_key_count(key)
            if self._on_evict: 
                self._on_evict(key=key, value=value, count=count, reason=reason)
            deregister_key(key)   

    def clear(self) -> None:
        with self._lock:
            items = list(self._store.items())
            if self._on_evict:
                for key, value in items:
                    count = memory_key_count(key)
                    self._on_evict(key, value, count)
                    deregister_key(key) 
            self._store.clear()

    def stats(self) -> list[tuple[str, int]]:
        with self._lock:
            result = [(k, memory_key_count(k)) for k in self._store]
        result.sort(key=lambda kv: kv[1], reverse=True) # sorted by hottest first:
        return result

    def keys(self) -> list[str]:
        with self._lock:
            return self._store.keys()