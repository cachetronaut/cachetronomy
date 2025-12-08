import asyncio
import time
import threading

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

def test_ttl_thread_stops_when_loop_closed(dummy_cache):
    """Test that TTL thread stops when event loop is closed."""
    loop = asyncio.new_event_loop()
    thread = TTLEvictionThread(
        cache=dummy_cache, loop=loop, ttl_cleanup_interval=0.05
    )
    thread.start()
    time.sleep(0.01)  # Let it start
    loop.close()  # Close the loop
    time.sleep(0.15)  # Wait for thread to detect and exit
    # Thread should exit because loop is closed
    assert not thread.is_alive()

def test_ttl_thread_handles_exception(dummy_cache):
    """Test that TTL thread handles exceptions in clear_expired."""
    class FailingCache:
        def __init__(self):
            self.call_count = 0

        def clear_expired(self):
            self.call_count += 1
            raise RuntimeError("Clear expired failed")

    failing_cache = FailingCache()
    loop = asyncio.new_event_loop()
    thread = TTLEvictionThread(
        cache=failing_cache, loop=loop, ttl_cleanup_interval=0.05
    )
    thread.start()
    time.sleep(0.15)
    thread.stop()
    thread.join(timeout=1)
    # Thread should have called clear_expired despite exceptions
    assert failing_cache.call_count >= 1
