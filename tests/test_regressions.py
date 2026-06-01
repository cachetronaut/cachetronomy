'''Regression tests for correctness fixes.'''
import time

import pytest

import cachetronomy.core.cache.cachetronaut as ctr
from cachetronomy.core.store.memory import MISS


@pytest.fixture
def cache(tmp_path_factory):
    db = tmp_path_factory.mktemp('db') / 'reg.db'
    c = ctr.Cachetronaut(db_path=str(db))
    yield c
    c.shutdown()


def test_expired_store_entry_not_served(cache):
    cache.set('k', {'v': 1}, time_to_live=1)
    cache.evict('k')          # drop from memory -> force the store path
    time.sleep(1.2)
    assert cache.get('k') is None


def test_expired_memory_entry_not_served(cache):
    cache.set('k', {'v': 1}, time_to_live=1)
    time.sleep(1.2)
    # Still resident in memory, but must be treated as expired, not stale-served.
    assert cache.get('k') is None


def test_memory_cap_enforced(cache):
    cache._memory.max_items = 2
    cache.set('a', 1)
    cache.set('b', 2)
    cache.set('c', 3)
    assert len(cache.memory_keys()) <= 2


def test_none_is_cacheable_via_decorator(cache):
    calls = {'n': 0}

    @cache
    def returns_none(x: int):
        calls['n'] += 1
        return None

    returns_none(1)
    returns_none(1)
    returns_none(1)
    assert calls['n'] == 1


def test_get_default_distinguishes_miss_from_cached_none(cache):
    cache.set('none_key', None, time_to_live=60)
    assert cache.get('none_key') is None
    assert cache.get('none_key', default=MISS) is None      # cached None -> hit
    assert cache.get('absent', default=MISS) is MISS         # genuine miss


def test_deserialize_model_from_store_path(cache):
    from pydantic import BaseModel

    class User(BaseModel):
        id: int
        name: str

    @cache
    def load_user(uid: int) -> User:
        return User(id=uid, name=f'user{uid}')

    load_user(7)
    cache.evict(load_user.key_for(7))   # force fetch from the store with a model
    result = load_user(7)
    assert isinstance(result, User) and result.id == 7


def test_delete_many_counts_only_existing(cache):
    cache.set('d1', 1)
    cache.set('d2', 2)
    assert cache.delete_many(['d1', 'd2', 'ghost']) == 2


def test_health_check_shape(cache):
    health = cache.health_check()
    assert health['status'] in {'healthy', 'degraded', 'unhealthy'}
    assert health['db_accessible'] is True
    assert 'memory_ok' in health and 'store_keys_count' in health
