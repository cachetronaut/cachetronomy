import threading
import asyncio
from typing import Callable, Any

class BaseBatchLogger:
    def __init__(
        self, 
        batch_fn: Callable[[list[Any]], Any], 
        batch_size: int =100, 
        flush_interval: float =0.5
    ):
        self.batch_fn = batch_fn
        self.batch_size = batch_size
        self.flush_interval = flush_interval
        self._buffer = []
        self.lock = threading.Lock()
        self._stopped = threading.Event()

    def _flush(self):
        with self.lock:
            if not self._buffer:
                return
            entries = list(self._buffer)
            self._buffer.clear()
        if entries:
            self.batch_fn(entries)

    def flush(self):
        self._flush()

    def stop(self):
        self._stopped.set()
        self.flush()

class AsyncBatchLogger(BaseBatchLogger):
    def __init__(
        self, 
        batch_fn: Callable[[list[Any]], Any], 
        flush_interval: float = 0.25,
        batch_size: int = 100
    ):
        super().__init__(batch_fn, batch_size, flush_interval)
        self._flush_task: asyncio.Task | None = None

    def start(self):
        if self._flush_task is not None and not self._flush_task.done():
            return
        self._stopped.clear()
        self._flush_task = asyncio.create_task(self._run())

    async def _run(self):
        while not self._stopped.is_set():
            await asyncio.sleep(self.flush_interval)
            await self.flush()

    async def log(self, entry):
        entries = []
        with self.lock:
            self._buffer.append(entry)
            if len(self._buffer) >= self.batch_size:
                entries = list(self._buffer)
                self._buffer.clear()
        if entries:
            result = self.batch_fn(entries)
            if asyncio.iscoroutine(result):
                await result

    async def flush(self):
        entries = []
        with self.lock:
            if self._buffer:
                entries = list(self._buffer)
                self._buffer.clear()
        if entries:
            result = self.batch_fn(entries)
            if asyncio.iscoroutine(result):
                await result

    async def stop(self):
        self._stopped.set()
        if self._flush_task:
            await self._flush_task
            self._flush_task = None
        await self.flush()

class SyncBatchLogger(BaseBatchLogger):
    def __init__(
        self, 
        batch_fn: Callable[[list[Any]], Any], 
        batch_size: int =100, 
        flush_interval: float = 0.25
    ):
        super().__init__(batch_fn, batch_size, flush_interval)
        self._timer: threading.Time | None = None
        self._timer_lock = threading.Lock()

    def _timer_flush(self):
        if not self._stopped.is_set():
            self.flush()
            self._start_timer()

    def log(self, entry):
        entries = []
        with self.lock:
            self._buffer.append(entry)
            if len(self._buffer) >= self.batch_size:
                entries = list(self._buffer)
                self._buffer.clear()
        if entries:
            self.batch_fn(entries)
        self._start_timer()

    def _start_timer(self):
        with self._timer_lock:
            if self._timer is not None:
                self._timer.cancel()
            if not self._stopped.is_set():
                self._timer = threading.Timer(self.flush_interval, self._timer_flush)
                self._timer.daemon = True
                self._timer.start()

    def start(self):
        self._stopped.clear()
        self._start_timer()

    def stop(self):
        self._stopped.set()
        with self._timer_lock:
            if self._timer is not None:
                self._timer.cancel()
                self._timer = None
        self.flush()