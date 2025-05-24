import asyncio
import time

from cachetronomy.core.eviction.time_to_live import TTLEvictionThread

def test_ttl_thread_invokes_clear_expired(dummy_cache):
    loop = asyncio.new_event_loop()
    thread = TTLEvictionThread(
        cache=dummy_cache, loop=loop, ttl_cleanup_interval=0.05
    )
    thread.start()
    time.sleep(0.12)
    thread.stop()
    assert dummy_cache._memory.stats()['clear_expired_called'] >= 1
