import threading
import logging
import asyncio
import inspect

class TTLEvictionThread(threading.Thread):
    def __init__(
        self,
        cache,
        loop: asyncio.AbstractEventLoop | None,
        ttl_cleanup_interval: int = 60,
    ):
        super().__init__(daemon=True, name='ttl_eviction_thread')
        self.cache = cache
        self._loop = loop or asyncio.get_event_loop()
        self.ttl_cleanup_interval = ttl_cleanup_interval
        self._stop_event = threading.Event()
        logging.debug('TTLEvictionThread initialized.')

    def _dispatch(self) -> None:
        if self._loop.is_closed():
            return
        maybe = self.cache.clear_expired()
        if inspect.isawaitable(maybe):
            future = asyncio.run_coroutine_threadsafe(maybe, self._loop)
            try:
                future.result()
            except Exception:
                logging.exception('Error in TTL cleanup')

    def run(self) -> None:
        try:
            self._dispatch()
        except Exception:
            logging.exception('TTLEvictionThread initial cleanup failed')
        while not self._stop_event.wait(self.ttl_cleanup_interval):
            try:
                self._dispatch()
            except Exception:
                logging.exception('TTLEvictionThread cleanup failed')

    def stop(self):
        self._stop_event.set()
