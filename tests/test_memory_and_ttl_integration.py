import asyncio
import time

from cachetronomy.core.eviction.memory import MemoryEvictionThread
from cachetronomy.core.eviction.time_to_live import TTLEvictionThread
from cachetronomy.core.access_frequency import promote_key
from tests.conftest import fake_mem

def test_ttl_and_memory_threads_coexist(monkeypatch, dummy_cache):
    for k in ('x', 'y'):
        dummy_cache._memory._store[k] = f'payload-{k}'
        promote_key(k)
    loop = asyncio.new_event_loop()
    ttl = TTLEvictionThread(cache=dummy_cache, loop=loop, ttl_cleanup_interval=0.03)
    mem = MemoryEvictionThread(
        cache=dummy_cache,
        loop=loop,
        memory_cleanup_interval=0.03,
        free_memory_target=20,  # MB
    )
    ttl.start()
    with fake_mem(monkeypatch, avail_mb=10):
        mem.start()
        time.sleep(0.11)
    ttl.stop()
    mem.stop()
    stats = dummy_cache._memory.stats()
    print(stats)
    assert stats['clear_expired_called'] >= 1
    assert stats['evicted'] >= 1
    dummy_cache.clear_all()
