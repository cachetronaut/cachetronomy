import threading
from collections import Counter
from typing import Callable


class AccessFrequencyTracker:
    def __init__(self) -> None:
        self._counts: Counter[str] = Counter()
        self._lock = threading.Lock()
        self._callback: Callable[[str], None] | None = None

    def register_callback(self, callback: Callable[[str], None]) -> None:
        self._callback = callback

    def promote(self, key: str) -> None:
        with self._lock:
            self._counts[key] += 1
        if self._callback:
            try:
                self._callback(key)
            except Exception:
                # Swallow exceptions in user-provided callback
                pass

    def deregister(self, key: str) -> None:
        with self._lock:
            self._counts.pop(key, None)

    def hot_keys(self, limit: int = 10) -> list[tuple[str, int]]:
        with self._lock:
            return self._counts.most_common(limit)

    def get_memory_count(self, key: str) -> int:
        with self._lock:
            return self._counts.get(key, 0)

# -- module-level convenience API --

_tracker = AccessFrequencyTracker()  # single global instance

def register_callback(callback: Callable[[str], None]) -> None:
    _tracker.register_callback(callback)

def promote_key(key: str) -> None:
    _tracker.promote(key)

def deregister_key(key: str) -> None:
    _tracker.deregister(key)

def hot_keys(limit: int = 10) -> list[tuple[str, int]]:
    return _tracker.hot_keys(limit)

def memory_key_count(key: str) -> int:
    return _tracker.get_memory_count(key)