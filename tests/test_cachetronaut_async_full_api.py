from __future__ import annotations

from datetime import timedelta

import pytest
import pytest_asyncio

import cachetronomy.core.cache.cachetronaut_async as ct_async
from cachetronomy.core.utils.time_utils import _now


# ---------------- fixture ---------------- #
@pytest_asyncio.fixture
async def async_cache(tmp_path_factory):
    db = tmp_path_factory.mktemp('db') / 'async.db'
    c = ct_async.AsyncCachetronaut(db_path=str(db))
    await c.init_async()
    yield c
    await c.shutdown()


async def _age(store, key: str, seconds: int):
    e = await store.get(key)
    e.expire_at = _now() - timedelta(seconds=seconds)
    await store.set(e)


# ---------- basic CRUD ------------- #
@pytest.mark.asyncio
async def test_set_get_delete(async_cache):
    await async_cache.set('α', 999)
    assert await async_cache.get('α') == 999
    await async_cache.evict('α')
    assert await async_cache.get('α') is None
    await async_cache.clear_all()


# ---------- full surface smoke pass ---------- #
@pytest.mark.asyncio
async def test_every_public_async_method_smoke(async_cache):
    # ── invalidation
    await async_cache.set('x', 1, tags=['a'])
    await async_cache.set('y', 2, tags=['a', 'b'])
    await async_cache.evict('x')
    await async_cache.evict_all()
    await async_cache.clear_all()
    await async_cache.clear_by_tags(['a'], exact_match=False)
    await async_cache.clear_by_profile('default')

    # ── expiry
    await async_cache.set('tmp', 'v', time_to_live=30)
    await _age(async_cache.store, 'tmp', 120)
    await async_cache.clear_expired()

    # ── inspection & logging
    await async_cache.memory_keys()
    await async_cache.store_keys()
    await async_cache.items()
    await async_cache.store_metadata()
    await async_cache.memory_stats()
    await async_cache.store_stats(limit=2)
    await async_cache.key_metadata('y')
    await async_cache.get('y')
    await async_cache.key_access_logs('y')
    await async_cache.access_logs()
    await async_cache.delete_access_logs('y')
    await async_cache.clear_access_logs()
    await async_cache.eviction_logs(limit=5)
    await async_cache.clear_eviction_logs()

    # ── profiles: needs **full kwargs** to satisfy store signature
    await async_cache.get_profile('qa')  # create if absent
    await async_cache.update_active_profile(
        time_to_live=7200,
        tags=['qa'],
        ttl_cleanup_interval=60,
        memory_based_eviction=True,
        free_memory_target=400.0,
        memory_cleanup_interval=5,
        max_items_in_memory=200,
    )
    await async_cache.list_profiles()
    await async_cache.delete_profile('qa')
    await async_cache.clear_all()
