from __future__ import annotations

import asyncio
from contextlib import contextmanager
from types import SimpleNamespace

import pytest


@pytest.fixture(scope='session')
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()

@pytest.fixture
def dummy_cache():
    class _Memory(SimpleNamespace):
        _store = {}
        def stats(self):
            return self._store.setdefault('_stats',
                                        {
                                            'clear_expired_called': 0, 
                                            'evicted': 0
                                        })

        def evict(self, key, *, reason='test'):
            if key in self._store:
                self._store.pop(key, None)
                # update the right dict ↓
                self.stats()['evicted'] += 1

    class Dummy(SimpleNamespace):
        _memory = _Memory()
        profile = SimpleNamespace(name='dummy')

        def clear_expired(self):
            self._memory.stats()['clear_expired_called'] += 1

        def clear_all(self):
            for k in list(self._memory._store.keys()):
                if not k.startswith('_'):
                    self._memory._store.pop(k, None)
            self._memory.stats()['evicted'] += 1

        def evicted(self):
            self._memory.stats()['evicted'] += 1

    return Dummy()

class _DummyThread:
    def __init__(self, *_, **__): ...
    def start(self): ...
    def stop(self): ...
    def join(self): ...

@pytest.fixture(autouse=True)
def _swap_threads(monkeypatch):
    import cachetronomy.core.cache.cachetronaut as ct

    monkeypatch.setattr(ct, 'TTLEvictionThread', _DummyThread, raising=True)
    monkeypatch.setattr(ct, 'MemoryEvictionThread', _DummyThread, raising=True)
    yield

@contextmanager
def fake_mem(monkeypatch, *, avail_mb: int, total_mb: int = 1024):
    import psutil

    class _VM:
        def __init__(self, avail, total):
            self.available = avail * 1024 ** 2
            self.total = total * 1024 ** 2

    monkeypatch.setattr(psutil, 'virtual_memory', lambda: _VM(avail_mb, total_mb))
    yield