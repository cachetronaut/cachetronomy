from __future__ import annotations

from datetime import timedelta

import pytest

import cachetronomy.core.cache.cachetronaut as ct
from cachetronomy.core.utils.time_utils import _now


@pytest.fixture
def cache(tmp_path_factory):
    db = tmp_path_factory.mktemp('db') / 'sync.db'
    c = ct.Cachetronaut(db_path=str(db))
    yield c
    c.shutdown()


# ----------------- helpers ----------------- #
def _age(store, key: str, seconds: int):
    e = store.get(key)
    e.expire_at = _now() - timedelta(seconds=seconds)
    store.set(e)


# ---------------- basic CRUD ---------------- #
def test_set_get_delete(cache):
    cache.set('foo', 'bar')
    assert cache.get('foo') == 'bar'
    cache.delete('foo')
    assert cache.get('foo') is None
    cache.clear_all()


def test_evict_and_evict_all(cache):
    cache.set('k1', 1)
    cache.set('k2', 2)
    cache.evict('k1')
    assert 'k1' not in cache.memory_keys()
    cache.evict_all()
    assert list(cache.memory_keys()) == []
    cache.clear_all()


# --------------- invalidation --------------- #
def test_clear_all(cache):
    cache.set('a', 1)
    cache.set('b', 2)
    cache.clear_all()
    assert not cache.memory_keys() and not cache.store_keys()
    cache.clear_all()


def test_clear_by_tags(cache):
    cache.set('x', 1, tags=['one'])
    cache.set('y', 2, tags=['one', 'two'])
    cache.clear_by_tags(['one'], exact_match=True)
    assert cache.get('x') is None and cache.get('y') == 2
    cache.clear_by_tags(['two'])
    assert cache.get('y') is None
    cache.clear_all()


def test_clear_by_profile(cache):
    cache.set('p-default', 1)
    cache.profile = 'alt'
    cache.set('p-alt', 2)
    cache.clear_by_profile('default')
    assert cache.get('p-default') is None and cache.get('p-alt') == 2
    cache.clear_all()


def test_clear_expired(cache):
    cache.set('tmp', 'data', time_to_live=10)
    _age(cache.store, 'tmp', 120)
    cache.clear_expired()
    assert cache.get('tmp') is None
    cache.clear_all()


# --------------- inspection ---------------- #
def test_metadata_and_stats(cache):
    cache.set('k', 42, tags=['num'])
    assert 'k' in (*cache.memory_keys(), *cache.store_keys())
    meta = cache.store_metadata()
    assert any(m.key == 'k' for m in meta)
    # store_stats may be empty but must return list
    assert isinstance(cache.store_stats(limit=3), list)
    cache.clear_all()


# --------------- logging ------------------- #
def test_access_and_eviction_logs(cache):
    cache.set('log-key', 123)
    cache.get('log-key')
    assert cache.key_access_logs('log-key')
    cache.delete_access_logs('log-key')
    cache.clear_access_logs()
    cache.clear_all()

    cache.evict('log-key')
    assert cache.eviction_logs()
    cache.clear_eviction_logs()
    cache.clear_all()


# --------------- profiles ------------------ #
def test_profile_lifecycle(cache):
    assert any(p.name == 'default' for p in cache.list_profiles())
    cache.delete_profile('default')
    assert not any(p.name == 'default' for p in cache.list_profiles())
    cache.get_profile('default')  # recreate
    cache.clear_all()
