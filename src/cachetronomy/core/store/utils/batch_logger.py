import inspect
import threading
import asyncio
from typing import Callable, Any

from synchronaut import synchronaut, get_preferred_loop

class BatchLogger():
    def __init__(
        self, 
        batch_fn: Callable[[list[Any]], Any], 
        batch_size: int = 200, 
        flush_interval: float | None = None,
        loop: asyncio.AbstractEventLoop | None = None,
    ):
        self.batch_fn = batch_fn
        self.batch_size = batch_size
        self.flush_interval = flush_interval or 5.0
        self._buffer = []
        self.lock = threading.Lock()
        self._stopped = threading.Event()
        self._flush_task: asyncio.Task | None = None
        self._loop = loop if isinstance(
            loop, asyncio.AbstractEventLoop
        ) else get_preferred_loop()

    @synchronaut()
    async def _flush(self):
        with self.lock:
            if not self._buffer:
                return
            entries = list(self._buffer)
            self._buffer.clear()
        if entries:
            self.batch_fn(entries)

    @synchronaut()
    async def start(self):
        if self._flush_task is not None and not self._flush_task.done():
            return
        self._stopped.clear()
        self._flush_task = self._loop.create_task(self._run())


    @synchronaut()
    async def _run(self):
        while not self._stopped.is_set():
            await asyncio.sleep(self.flush_interval)
            await self.flush()

    @synchronaut()
    async def log(self, entry):
        entries = []
        with self.lock:
            self._buffer.append(entry)
            if len(self._buffer) >= self.batch_size:
                entries = list(self._buffer)
                self._buffer.clear()
        if not entries:
            return
        result = self.batch_fn(entries)
        if inspect.isawaitable(result):
            await result

    @synchronaut()
    async def flush(self):
        entries = []
        with self.lock:
            entries = list(self._buffer)
            self._buffer.clear()
        if not entries:
            return
        result = self.batch_fn(entries)
        if inspect.isawaitable(result):
            await result

    @synchronaut()
    async def stop(self):
        self._stopped.set()
        if self._flush_task and not self._flush_task.done():
            # Cancel the task and wait for it to finish on its own loop
            self._flush_task.cancel()
            # Don't await - just let it cancel, as it may be on a different loop
            self._flush_task = None
        await self.flush()