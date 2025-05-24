import threading
import psutil
import logging
import asyncio
import inspect

from cachetronomy.core.access_frequency import hot_keys


class MemoryEvictionThread(threading.Thread):
    def __init__(
        self,
        cache,
        loop: asyncio.AbstractEventLoop | None,
        memory_cleanup_interval: float,
        free_memory_target: float,
    ):
        super().__init__(daemon=True, name='memory_eviction_thread')
        self.cache = cache
        self.loop = loop
        self.memory_cleanup_interval = memory_cleanup_interval
        self.free_memory_target = free_memory_target
        self._stop_event = threading.Event()

    def _available_mb(self) -> float:
        return psutil.virtual_memory().available / (1024 ** 2)

    def _determine_keys_to_evict(self) -> list[str]:
        keys_to_evict: list[str] = []
        for key, *_ in reversed(hot_keys(limit=9999)):
            if key not in self.cache._memory._store:
                continue
            keys_to_evict.append(key)
        return keys_to_evict

    def evict(self) -> None:
        available_mb = self._available_mb()
        total_mb = psutil.virtual_memory().total / (1024 ** 2)
        threshold_mb = (
            total_mb * self.free_memory_target
            if self.free_memory_target <= 1
            else self.free_memory_target
        )
        if available_mb > threshold_mb:
            return
        for key in self._determine_keys_to_evict() or []:
            if key not in self.cache._memory._store:
                continue
            self.cache._memory.evict(key, reason='memory_eviction')
            available_mb = self._available_mb()
            if available_mb > threshold_mb:
                return

    def run(self):
        while not self._stop_event.is_set():
            try:
                if inspect.iscoroutinefunction(self.evict):
                    asyncio.run_coroutine_threadsafe(
                        self.evict(), 
                        self.loop
                    ).result()
                else:
                    self.evict()
            except Exception:
                logging.exception(
                    'MemoryEvictionThread encountered an error during eviction.'
                )
            if self._stop_event.wait(self.memory_cleanup_interval):
                break

    def stop(self):
        logging.debug(
            'Shutting down MemoryEvictionThread and evicting remaining keys.'
                      )
        for key in self._determine_keys_to_evict() or []:
            self.cache._memory.evict(key, reason='shutdown')
        self._stop_event.set()
