from types import SimpleNamespace

import pytest

import cachetronomy.core.cache.cachetronaut as ctr

class _FakeStore:
    '''Duck-type store that gives Cachetronomer something to call.'''
    def __getattr__(self, name):
        async def _async_noop(*args, **kwargs):
            return None
        return _async_noop

def _noop(*_a, **_kw):
    '''Shared do-nothing helper so we don’t repeat `pass`.'''
    return None

class TinyCache(ctr.Cachetronaut):
    def __init__(self):
        super().__init__(
            max_items_in_memory=None,
        )
        self.store=_FakeStore()
        self.time_to_live = getattr(super(), 'default_time_to_live', None)
        self.tags = getattr(super(), 'tags', None)

    def store_keys(self, *_a, **_kw):     
        return []
    def access_logs(self, *_a, **_kw):    
        return []
    def get_profile(self, *_a, **_kw):    
        return None
    def list_profiles(self, *_a, **_kw):  
        return []
    def items(self):                      
        return self._memory._store
    def memory_keys(self, *_a, **_kw):    
        return list(self._memory._store)
    def key_access_logs(self, *_a, **_kw):
        return []
    def store_metadata(self, *_a, **_kw): 
        return {}
    def key_metadata(self, *_a, **_kw):
        return {}
    clear_access_logs = delete_access_logs = access_logs
    eviction_logs = clear_eviction_logs = access_logs
    evict = delete = clear_all = clear_by_tags = clear_by_profile = clear_expired = _noop
    evict_all = shutdown = _noop
    delete_profile = _noop

@pytest.fixture
def fake_store(monkeypatch):
    '''Patch MemoryCache inside Cachetronomer with a super-simple dict.'''
    fake = {'_store': {}}
    class FakeMemory(SimpleNamespace):
        _store = fake['_store']
        def __init__(self, *args, **kwargs):
            pass
        def __contains__(self, k):
            return k in self._store
        def __getitem__(self, k):
            return self._store[k]
        def __setitem__(self, k, v):
            self._store[k] = v
        def set(self, k, v):
            self.__setitem__(k, v)
        async def get(self, key):
            return self._store.get(key, None)
        def stats(self):
            return {'size': len(self._store)}
    import cachetronomy.core.cache.cachetronaut as ctr
    monkeypatch.setattr(ctr, 'MemoryCache', FakeMemory)
    return fake['_store']

def test_decorator_caches_return_value(fake_store):
    c = TinyCache()
    @c(prefer='orjson')
    def add(a: int, b: int) -> int:
        return a + b
    
    add_result = add(1, 2)
    assert add_result == 3 # calculated
    assert add(1, 2) == 3 # cached
    assert len(fake_store.items()) == 1