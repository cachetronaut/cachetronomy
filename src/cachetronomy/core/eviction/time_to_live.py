import threading
import logging
import asyncio

from synchronaut import get_preferred_loop, call_any

class TTLEvictionThread(threading.Thread):
    def __init__(
        self,
        cache,
        loop: asyncio.AbstractEventLoop | None,
        ttl_cleanup_interval: int = 60,
    ):
        super().__init__(daemon=True, name='ttl_eviction_thread')
        self.cache = cache
        self.loop = loop or get_preferred_loop()
        self.ttl_cleanup_interval = ttl_cleanup_interval
        self._stop_event = threading.Event()
        logging.debug('TTLEvictionThread initialized.')

    def run(self) -> None:
        while not self._stop_event.wait(self.ttl_cleanup_interval):
            if self.loop.is_closed():
                return
            try:
                call_any(self.cache.clear_expired)
            except Exception:
                logging.exception('TTL cleanup failed')

    def stop(self):
        self._stop_event.set()
