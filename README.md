# Cachetronomy
A lightweight, SQLite-backed cache for Python with first-class sync **and** async support. Features TTL and memory-pressure eviction, persistent hot-key tracking, pluggable serialization, a decorator API and a CLI (coming soon).

## Why Cachetronomy?
- **Persistent**: stores all entries in SQLite; survives process restarts, no separate server.
- **Sync & Async**: one API shape for both `Cachetronaut` (sync) and `AsyncCachetronaut` (async).
- **Smart Eviction**: TTL expiry and RAM-pressure eviction via background threads.
- **Hot-Key Tracking**: logs every read in memory and SQLite; query top-N hotspots.
- **Flexible Serialization**: JSON, orjson, MsgPack out-of-the-box; swap in your own.
- **Decorator API**: wrap any function or coroutine to cache its results automatically.

## 🚀 Installation
```bash
pip install cachetronomy
# for orjson & msgpack support:
pip install cachetronomy[fast]
```

## 📦 Core Features
### Cache clients
- **Sync**: `from cachetronomy.core.cache.cachetronaut import Cachetronaut`
- **Async**: `from cachetronomy.core.cache.cachetronaut_async import AsyncCachetronaut`
Both share almost 1:1 APIs:
### Decorator API
```python
cachetronaut = Cachetronaut(db_path="cache.db")
@cachetronaut(ttl=60, tags=["fib"])
def fib(n: int) -> int:
    return fib(n-1) + fib(n-2) if n>1 else 1
```
```python
acachetronaut = AsyncCachetronaut(db_path="async.db")
await acachetronaut.init_async()
@acachetronaut(ttl=120)
async def fetch(id: int) -> dict:
    ...
```
Behind the scenes it:
1. Builds a key via your `key_builder` (default: module+fn+args).
2. `get(key)` → hit returns cached; miss runs the fn.
3. Stores via `set(key, payload, fmt, expire_at, tags, profile)`.

## ⚙️ Profiles & Settings
All defaults come from a Pydantic `CacheSettings`, override via environment variables or `.env`:
```dotenv
CACHE_DB_PATH=/tmp/cache.db
CACHE_DEFAULT_PROFILE=analytics
CACHE_TTL_CLEANUP_INTERVAL=30
CACHE_MEMORY_BASED_EVICTION=true
CACHE_FREE_MEMORY_TARGET=200.0
CACHE_MEMORY_CLEANUP_INTERVAL=5
CACHE_MAX_ITEMS_IN_MEMORY=100
```
Profiles let you switch TTL, eviction rules, tags at runtime:
```python
from cachetronomy.core.types.profiles import Profile
p = Profile(
  name="customer",
  time_to_live=120,
  tags=["public"],
  ttl_cleanup_interval=15,
  memory_based_eviction=True,
  free_memory_target=100.0,
  memory_cleanup_interval=2,
  max_items_in_memory=50,
)
cache.profile = p           # sync
await async_cache.set_profile(p)  # async
cache.profile = "customer"  # by name
```

## 🔄 Eviction
### TTL Eviction
A background `TTLEvictionThread` wakes every `ttl_cleanup_interval` and calls `clear_expired()`.
Expired entries are removed from both SQLite and in-memory.
### Memory-Pressure Eviction
A daemon `MemoryEvictionThread` polls `psutil.virtual_memory().available`.
When under your `free_memory_target` (MB), it evicts the coldest keys (via access-frequency) until you’re back above the threshold.
You can also drive eviction manually:
```python
from cachetronomy.core.eviction.memory import MemoryEvictionThread
thread = MemoryEvictionThread(cache, loop=None, memory_cleanup_interval=1, free_memory_target=100.0)
thread.evict()  # one pass
thread.stop()
```

## 🔥 Hot-Key Tracking
Each `get()` call logs:
- In-memory counter (fast)
- SQLite table (persistent)
APIs:
```python
from cachetronomy.core.access_frequency import get_hot_keys
print(get_hot_keys(5))  # in-memory top-5
print(cache.store.get_all_access_logs())    # raw DB rows
print(cache.get_hot_keys(limit=5))          # uses DB
```

## 🛠 Serialization
Default order:
1. **orjson** if installed & type is JSON-compatible
2. **msgpack** if installed & data is bytes/large
3. **std json** fallback
Usage:
```python
from cachetronomy.core.serialization import serialize, deserialize
payload, fmt = serialize(obj, prefer="msgpack")
obj2 = deserialize(payload, fmt, model_type=MyPydanticModel)
```
Override globally with `CACHE_SERIALIZER=json|orjson|msgpack`.

## 🧪 Development & Testing
```bash
git clone https://github.com/cachetronaut/cachetronomy.git
cd cachetronomy
pip install -r requirements-dev.txt
pytest
```
We aim for **100% parity** between sync and async clients; coverage includes TTL, memory eviction, decorator, profiles, serialization and logging.

## 🤝 Contributing
1. Fork & branch
2. Add tests for new features
3. Submit a PR

## 📄 License
MIT — see [LICENSE](https://github.com/cachetronaut/cachetronomy/blob/main/LICENSE) for details.