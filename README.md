# Cachetronomy
A lightweight, SQLite-backed cache for Python with first-class sync **and** async support. Features TTL and memory-pressure eviction, persistent hot-key tracking, pluggable serialization, a decorator API and a CLI.

[![Package Version](https://img.shields.io/pypi/v/cachetronomy.svg)](https://pypi.org/project/cachetronomy/) | [![Supported Python Versions](https://img.shields.io/pypi/pyversions/cachetronomy.svg)](https://pypi.org/project/cachetronomy/)
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
- **Sync**: `from cachetronomy import Cachetronaut`
- **Async**: `from cachetronomy import AsyncCachetronaut`
Both share almost 1:1 APIs:
### Decorator API
```python
import time
from cachetronomy import Cachetronaut

cachetronaut: Cachetronaut = Cachetronaut(db_path="cachetronomy.db")

@cachetronaut(time_to_live=3600)  # cache each quote for one hour
def pull_quote_from_film(actor: str, film: str) -> str:
    # your “expensive” lookup logic goes here
    # for demonstration we just sleep and return a hard-coded quote
    time.sleep(10) # time in seconds
    return (
        '''
        The path of the righteous key is beset on all sides
		by stale entries and the tyranny of cold fetches.
		
		Blessed is he who, in the name of latency and hit-rates,
		shepherds the hot through the valley of disk I/O,
		for he is truly the keeper of throughput and the finder of
		lost lookups.
		
		And I will strike down upon thee with great vengeance and
		furious eviction those who try to poison my cache.
		
		And you will know my name is Cache when I lay my lookups upon thee!
		'''
    )

# First call → cache miss, runs the function
quote1 = pull_quote_from_film("Samuel L. Cacheson", "Action Jackson")

# Subsequent call within the TTL → cache hit, returns instantly
quote2 = pull_quote_from_film("Samuel L. Cacheson", "Action Jackson")
assert quote1 is quote2  # same object from cache

# If you really need to force eviction or clear expired entries, call them yourself:
cachetronaut.evict("pull_quote_from_film:('Samuel L. Cacheson','Action Jackson')")
cachetronaut.clear_expired()

# OR TRY IT ASYNC

import asyncio
from typing import Any, Dict
from cachetronomy import AsyncCachetronaut

async def main():
    # 1. Init your async client
    acachetronaut = AsyncCachetronaut(db_path="cachetronomy.db")
    await acachetronaut.init_async()

    # 2. Decorate your coroutine—cache results for 10 minutes
    @acachetronaut(time_to_live=600)
    async def become_cachémon_master(id: int) -> Dict[str, Any]:
        print('Welcome to the wonderful world of Cachémon...')
        await asyncio.sleep(1)
        print('Pick your starter Cachémon, I'd start with a 🔥 type...')
        await asyncio.sleep(1)
        print('Go get that first gym badge...')
        await asyncio.sleep(1)
        print('Go get the next seven gym badges...')
        await asyncio.sleep(2)
        print('Beat Blue (for the 100th time)...')
        await asyncio.sleep(1)
        print('Also, you are gonna train if you want to get to the E4...')
        await asyncio.sleep(3)
        print('Now you got to beat the E4...')
        await asyncio.sleep(1)
        print('You did it! you are a Cachémon master!')
        return {
            "id": id,
            "name": "Ash Cache-um",
            "type": "Person",
            "known_for": "Trying to cache ’em al",
            "cachémon": [
                {"name": "Picacheu",   "type": "cachémon", "known_for": "Shocking retrieval speeds ⚡️"},
                {"name": "Sandcache",  "type": "cachémon", "known_for": "Slashing latency with sharp precision ⚔️"},
                {"name": "Rapicache",  "type": "cachémon", "known_for": "Blazing-fast data delivery 🔥"},
                {"name": "Cachecoon",  "type": "cachémon", "known_for": "Securely cocooning your valuable data 🐛"},
                {"name": "Cachedform", "type": "cachémon", "known_for": "Adapting to any data climate ☁️☀️🌧️"},
                {"name": "Cachenea",   "type": "cachémon", "known_for": "Pinpointing the freshest data points 🌵"},
                {"name": "Cacheturne", "type": "cachémon", "known_for": "Fetching data, even in the darkest queries 🌙"},
                {"name": "Cacherain",  "type": "cachémon", "known_for": "Intimidating load times with swift patterns 🦋"},
                {"name": "Snor-cache", "type": "cachémon", "known_for": "Waking up just in time to serve warm data 😴"},
                ...
            ],
        }

    # 3. On first call → cache miss, runs the coroutine
    trainer1 = await cachemon_trainer(1301)

    # 4. Subsequent call within TTL → cache hit, returns instantly
    trainer2 = await cachemon_trainer(1301)
    assert trainer1 is trainer2  # same object from cache

    # 5. If you need to evict or purge expired entries manually:
    await acachetronaut.evict("become_cachémon_master(1301)")
    await acachetronaut.clear_expired()

    # 6. Graceful shutdown when you’re done
    await acachetronaut.shutdown()


asyncio.run(main())
```

## Under the Hood: Core Mechanisms and Code References

| Mechanism                    | How It Works                                                                                                                                                                                                   | Code Reference                                                                                      |
| ---------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------- |
| **Key Building**             | The decorator’s `__call__` wraps your function and—via the shared `Cachetronomer` base—uses the default `key_builder` to form a key string of the form `fn(args)` – order independent.                         | `cachetronomer.py` → `__call__` → calls `key_builder.build(...)`                                    |
| **Cache Lookup**             | In `get()`, first checks `self._memory.get(key)`; on a miss it awaits `self.store.get(key)`, evicts stale entries, then returns `None` or the loaded value.                                                    | `cachetronaut.py` & `cachetronaut_async.py` → `get()`                                               |
| **Storage**                  | After a miss, `set()` serializes via `serialize()`, puts the value into in-memory LRU, then writes a `CacheEntry` into SQLite with TTL, tags, profile, etc.                                                    | `cachetronaut.py` & `cachetronaut_async.py` → `set()`                                               |
| **Profiles & Settings**      | The sync `@profile.setter` (and async `._set_profile` via your setter) loads or upserts a `Profile` row, then calls `_apply_profile_settings()` to update TTL, eviction intervals, tags, and restarts threads. | `cachetronaut.py` → `@profile.setter`;`cachetronaut_async.py` → `profile.setter` & `_set_profile()` |
| **TTL Eviction**             | A daemon `TTLEvictionThread` sleeps `ttl_cleanup_interval` seconds, then calls `cache.clear_expired()` (via `run_coroutine_threadsafe` in async) to purge expired rows.                                        | `core/eviction/time_to_live.py` → `TTLEvictionThread.run()` & `_dispatch()`                         |
| **Memory-Pressure Eviction** | A daemon `MemoryEvictionThread` polls `psutil.virtual_memory().available` every `memory_cleanup_interval` seconds and evicts the coldest keys via access-frequency until free memory ≥ target.                 | `core/eviction/memory.py` → `MemoryEvictionThread.run()`                                            |
| **Manual Eviction**          | Public methods `evict(key)`, `clear_by_tags(...)`, and `clear_by_profile(...)` call into the in-memory cache and/or store delete APIs, logging eviction events where appropriate.                              | `cachetronaut.py` & `cachetronaut_async.py` → `evict()`, `clear_*()`                                |
| **Hot-Key Tracking**         | On every `get()`, a callback registered in initialization logs an `AccessLogEntry` both in memory (fast counter) and—via `store.log_access()`—persistently to SQLite.                                          | `cachetronomer.py` registration in constructor;`cachetronaut_async.py` in `init_async()`            |
| **Serialization**            | `set()` calls `serialize(value, prefer=…)`, which picks `orjson`, `msgpack`, or std `json` based on type and availability, and records the `fmt` in the DB.                                                    | `core/serialization.py` → `serialize()`;`cachetronaut*.py` → usage in `set()`                       |

>`Cachetronomer` is the shared base class that encapsulates core caching logic—like memory store management, key building, and eviction hooks—used by both the synchronous and asynchronous cache clients.

# Cachetronomy API
Quick overview of the public API for both sync (`Cachetronaut`) and async (`AsyncCachetronaut`) clients:

| Method                  | Cachetronaut                      | AsyncCachetronaut                 | Description                                                                                           |
| ----------------------- | --------------------------------- | --------------------------------- | ----------------------------------------------------------------------------------------------------- |
| `__init__`              | `__init__(db_path, …)`            | `__init__(db_path, …)`            | Construct a new cache client with the given database path and settings.                               |
| `init_async`            | —                                 | `init_async()`                    | (Async only) Initialize any async-specific internals (e.g. connections).                              |
| `shutdown`              | `shutdown()`                      | `shutdown()`                      | Gracefully stop eviction threads and close the underlying store.                                      |
| `set`                   | `set(key, payload, …)`            | `set(key, payload, …)`            | Store a value under `key` with optional TTL, tags, serializer, etc.                                   |
| `get`                   | `get(key, …)`                     | `get(key, …)`                     | Retrieve a cached entry (or `None` if missing/expired), optionally unmarshaled into a Pydantic model. |
| `delete`                | `delete(key)`                     | `delete(key)`                     | Remove the given key from the cache immediately.                                                      |
| `evict`                 | `evict(key)`                      | `evict(key)`                      | Same as `delete` but also logs an eviction event.                                                     |
| `store_keys`            | `store_keys()`                    | `store_keys()`                    | Return a list of all keys currently persisted in SQLite.                                              |
| `memory_keys`           | `memory_keys()`                   | `memory_keys()`                   | Return a list of all keys currently held in the in-process memory cache.                              |
| `all_keys`              | `all_keys()`                      | `all_keys()`                      | List every key in both memory and store.                                                              |
| `key_metadata`          | `key_metadata(key)`               | `key_metadata(key)                | Fetch the metadata (TTL, serialization format, tags, version, etc.) for a single cache key.           |
| `store_metadata`        | `store_metadata()`                | `store_metadata()`                | Retrieve a list of metadata objects for every entry in the persistent store.                          |
| `items`                 | `items()`                         | `items()`                         | List every item in both memory and store.                                                             |
| `evict_all`             | `evict_all()`                     | `evict_all()`                     | Evict every entry (logs each eviction) but leaves table structure intact.                             |
| `clear_all`             | `clear_all()`                     | `clear_all()`                     | Delete all entries from both memory and store without logging individually.                           |
| `clear_expired`         | `clear_expired()`                 | `clear_expired()`                 | Purge only those entries whose TTL has elapsed.                                                       |
| `clear_by_tags`         | `clear_by_tags(tags)`             | `clear_by_tags(tags)`             | Remove entries matching any of the provided tags.                                                     |
| `clear_by_profile`      | `clear_by_profile(name)`          | `clear_by_profile(name)`          | Remove all entries that were saved under the given profile name.                                      |
| `memory_stats`          | `memory_stats(limit)`             | `memory_stats(limit)`             | Return the top-N hottest keys by in-memory access count.                                              |
| `store_stats`           | `store_stats(limit)`              | `store_stats(limit)`              | Return the top-N hottest keys by persisted access count.                                              |
| `access_logs`           | `access_logs()`                   | `access_logs()`                   | Fetch raw access-log rows from SQLite for detailed inspection.                                        |
| `key_access_logs`       | `key_access_logs(key)`            | `key_access_logs(key)`            | Fetch all access-log entries for a single key.                                                        |
| `clear_access_logs`     | `clear_access_logs()`             | `clear_access_logs()`             | Delete all access-log rows from the database.                                                         |
| `delete_access_logs`    | `delete_access_logs(key)`         | `delete_access_logs(key)`         | Delete all access-log rows for the given key.                                                         |
| `eviction_logs`         | `eviction_logs(limit)`            | `eviction_logs(limit)`            | Fetch recent eviction events (manual, TTL, memory-pressure, etc.).                                    |
| `clear_eviction_logs`   | `clear_eviction_logs()`           | `clear_eviction_logs()`           | Delete all recorded eviction events.                                                                  |
| `profile`               | `@property` & `@profile.setter`   | `@property` & `@profile.setter`   | Get or switch to a named Profile, applying its settings and restarting eviction threads.              |
| `update_active_profile` | `update_active_profile(**kwargs)` | `update_active_profile(**kwargs)` | Modify the active profile’s settings in-place and persist them.                                       |
| `get_profile`           | `get_profile(name)`               | `get_profile(name)`               | Load the settings of a named profile without applying them.                                           |
| `delete_profile`        | `delete_profile(name)`            | `delete_profile(name)`            | Remove a named profile from the `profiles` table.                                                     |
| `list_profiles`         | `list_profiles()`                 | `list_profiles()`                 | List all saved profiles available in the `profiles` table.                                            |

# Cachetronomy Tables
Here's a breakdown of the **tables and columns** you will have in your `cachetronomy` cache.
### 🗃️ `cache`
Stores serialized cached objects, their TTL metadata, tags, and versioning.

|Column |Type |Description |
|------------------|------------|----------------------------------------------------|
|`key` |TEXT (PK 🔑)|Unique cache key |
|`data` |BLOB |Serialized value (orjson, msgpack, json) |
|`fmt` |TEXT |Serialization format used |
|`expire_at` |DATETIME |UTC expiry time. |
|`tags` |TEXT |Serialized list of tags (usually JSON or CSV format)|
|`version` |INTEGER |Version number for schema evolution/versioning |
|`saved_by_profile`|TEXT |Profile name that created or last updated this entry|
### 🧾 `access_log`
Tracks when a key was accessed and how frequently.

| Column | Type | Description |
| -------------------------- | ------------ | --------------------------------- |
| `key` | TEXT (PK 🔑) | Cache key |
| `access_count` | INTEGER | Number of times accessed |
| `last_accessed` | DATETIME | Most recent access time |
| `last_accessed_by_profile` | TEXT | Profile that made the last access |
### 🚮 `eviction_log`
Tracks key eviction events and their reasons (manual, TTL, memory, tag).

|Column |Type |Description |
|--------------------|---------------|------------------------------------------------------------|
|`id` |INTEGER (PK 🔑)|Autoincrement ID |
|`key` |TEXT |Evicted key |
|`evicted_at` |DATETIME |Timestamp of eviction |
|`reason` |TEXT |Reason string (`"manual_eviction"`, `"time_eviction"`, etc.)|
|`last_access_count` |INTEGER |Final recorded access count before eviction |
|`evicted_by_profile`|TEXT |Name of profile that triggered the eviction |
### 📋 `profiles`
Holds saved profile configurations for future reuse.

| Column                    | Type         | Description                                       |
| ------------------------- | ------------ | ------------------------------------------------- |
| `name`                    | TEXT (PK 🔑) | Unique profile name                               |
| `time_to_live`            | INTEGER      | Default TTL for entries                           |
| `ttl_cleanup_interval`    | INTEGER      | Frequency in seconds to run TTL cleanup           |
| `memory_based_eviction`   | BOOLEAN      | Whether memory pressure-based eviction is enabled |
| `free_memory_target`      | REAL         | MB of free RAM to maintain                        |
| `memory_cleanup_interval` | INTEGER      | How often to check system memory                  |
| `max_items_in_memory`     | INTEGER      | Cap for in-RAM cache                              |
| `tags`                    | TEXT         | Default tags for all entries in this profile      |
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