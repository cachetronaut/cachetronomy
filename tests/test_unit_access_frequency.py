from cachetronomy.core.access_frequency import (
    promote_key,
    hot_keys,
    memory_key_count,
    register_callback,
)

def test_promote_and_counts():
    promote_key('alpha')
    promote_key('alpha')
    promote_key('alpha')
    promote_key('beta')
    promote_key('beta')
    assert memory_key_count('alpha') == 3
    assert memory_key_count('beta') == 2
    print(hot_keys(2))
    assert hot_keys(2) == [('alpha', 3), ('beta', 2)]

def test_callback_fires(monkeypatch):
    fired = {}
    register_callback(lambda k: fired.setdefault(k, 0) or fired.update({k: 1}))
    promote_key('gamma')
    assert fired == {'gamma': 1}
