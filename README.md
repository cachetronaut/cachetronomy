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
### 🧑‍🚀 Cache clients
```python
# For Sync Client
from cachetronomy import Cachetronaut

# For Async Client
from cachetronomy import AsyncCachetronaut
```
### 🎍 Decorator API
```python
import time
import asyncio

from cachetronomy.core.types.schemas import CacheEntry

_ = '\n.'*5

def sync_main():
    print('\n# ––– Sync Client Test –––')
    from cachetronomy import Cachetronaut

    cachetronaut: Cachetronaut = Cachetronaut(db_path='cachetronomy.db')
    cachetronaut.clear_all()

    items: list[CacheEntry] = cachetronaut.items()
    print([item.model_dump() for item in items]) # no items

    @cachetronaut(time_to_live=3600)  # cache each quote for one hour
    def pull_quote_from_film(actor: str, film: str) -> str:
        # Your “expensive” lookup logic goes here
        # For demonstration we just sleep and return a hard-coded quote
        time.sleep(2) # time in seconds
        quote = 'The path of the righteous key is beset on all sidesby stale entries and the tyranny of cold fetches. Blessed is he who, in the name of latency and hit-rates, shepherds the hot through the valley of disk I/O, for he is truly the keeper of throughput and the finder oflost lookups. And I will strike down upon thee with great vengeance and furious eviction those who try to poison my cache. And you will know my name is Cache when I lay my lookups upon thee!'
        return quote

    # First call → cache miss, runs the function
    quote1 = pull_quote_from_film('Samuel L. Cacheson', 'Action Jackson')

    # Subsequent call within the TTL → cache hit, returns instantly
    quote2 = pull_quote_from_film('Samuel L. Cacheson', 'Action Jackson')
    print(f'{quote2 = }',_)
    print(f'{quote1 is quote2 = }',_)

    # If you really need to force eviction or clear expired entries, call them yourself:
    print(f'{cachetronaut.get('pull_quote_from_film(actor=\'Samuel L. Cacheson\', film=\'Action Jackson\')')= }',_)
    cachetronaut.evict('pull_quote_from_film:(\'Samuel L. Cacheson\',\'Action Jackson\')')
    cachetronaut.clear_expired()
    print(f'{cachetronaut.get('pull_quote_from_film(actor=\'Samuel L. Cacheson\', film=\'Action Jackson\')')= }',_)

# OR TRY IT ASYNC

async def async_main():
    print('\n# ––– Async Client Test –––')
    from typing import Any, Dict
    from cachetronomy import AsyncCachetronaut

    # 1. Init your async client
    acachetronaut = AsyncCachetronaut(db_path='cachetronomy.db')
    await acachetronaut.init_async()
    await acachetronaut.clear_all()

    # 2. Decorate your coroutine—cache results for 10 minutes
    @acachetronaut(time_to_live=600)
    async def gotta_cache_em_all(id: int) -> Dict[str, Any]:
        print('Welcome to the wonderful world of Cachémon.', _)
        await asyncio.sleep(1)
        print('Pick your starter Cachémon, I\'d start with a 🔥 type.', _)
        await asyncio.sleep(1)
        print('Go get that first gym badge.', _)
        await asyncio.sleep(1)
        print('Go get the next seven gym badges.', _)
        await asyncio.sleep(2)
        print('Beat Blue (for the 100th time).', _)
        await asyncio.sleep(1)
        print('Also, you are gonna train if you want to get to the E4.', _)
        await asyncio.sleep(3)
        print('Now you got to beat the E4.', _)
        await asyncio.sleep(1)
        print('You did it! you are a Cachémon master!', _)
        return {
            'id': id,
            'name': 'Ash Cache-um',
            'type': 'Person',
            'known_for': 'Trying to cache ’em al',
            'cachémon': [
                {'name': 'Picacheu',   'type': 'cachémon', 'known_for': 'Shocking retrieval speeds ⚡️'},
                {'name': 'Sandcache',  'type': 'cachémon', 'known_for': 'Slashing latency with sharp precision ⚔️'},
                {'name': 'Rapicache',  'type': 'cachémon', 'known_for': 'Blazing-fast data delivery 🔥'},
                {'name': 'Cachecoon',  'type': 'cachémon', 'known_for': 'Securely cocooning your valuable data 🐛'},
                {'name': 'Cachedform', 'type': 'cachémon', 'known_for': 'Adapting to any data climate ☁️☀️🌧️'},
                {'name': 'Cachenea',   'type': 'cachémon', 'known_for': 'Pinpointing the freshest data points 🌵'},
                {'name': 'Cacheturne', 'type': 'cachémon', 'known_for': 'Fetching data, even in the darkest queries 🌙'},
                {'name': 'Cacherain',  'type': 'cachémon', 'known_for': 'Intimidating load times with swift patterns 🦋'},
                {'name': 'Snor-cache', 'type': 'cachémon', 'known_for': 'Waking up just in time to serve warm data 😴'},
            ],
            'cachémon_champion': True,
            'cachémon_champion_date': time.ctime(),
        }
    
    # 3. On first call → cache miss, runs the coroutine
    trainer1 = await gotta_cache_em_all(1301)
    print(f'{trainer1 = }',_)

    # 4. Second call within TTL → cache hit (returns instantly)
    trainer2 = await gotta_cache_em_all(1301)
    print(f'{trainer2 = }',_)

    print(f'{trainer1 is trainer2 = }',_)
    print(f'{await acachetronaut.get('gotta_cache_em_all(id=1301)') = }',_)

    # 5. Manual eviction or cleanup
    await acachetronaut.evict('gotta_cache_em_all(id=1301)')
    await acachetronaut.clear_expired()
    print(f'{await acachetronaut.get('gotta_cache_em_all(id=1301)') = }',_)

    await acachetronaut.shutdown()

if __name__ == "__main__":
    sync_main()
    asyncio.run(async_main())
```

## ⚙ Under the Hood: Core Mechanisms and Code References
| Mechanism                    | How It Works                                                                                                              |
| ---------------------------- | --------------------------------------------------------------------------------------------------------------------------|
| **Key Building**             | Generates a consistent, order-independent key from the function name and its arguments.                                   |
| **Cache Lookup**             | On `get()`, check the in-memory cache first; if the entry is missing or stale, continues to the next storage layer.       |
| **Storage**                  | On `set()`, stores the newly computed result both in memory (for speed) and in a small on-disk database (for persistence).|
| **Profiles & Settings**      | Lets you switch between saved caching profiles and settings without disrupting running code.                              |
| **TTL Eviction**             | A background task periodically deletes entries that have exceeded their time-to-live.                                     |
| **Memory-Pressure Eviction** | Another background task frees up space by evicting the least-used entries when available system memory gets too low.      |
| **Manual Eviction**          | Helper methods allow you to remove individual keys or groups of entries whenever you choose.                              |
| **Hot-Key Tracking**         | Records how frequently each key is accessed so the system knows which items are most important to keep.                   |
| **Serialization**            | Converts data into a compact binary or JSON-like format before writing it to storage, and remembers which format it used. |
# 🗨 Cachetronomy API
Quick overview of the public API for both sync (`Cachetronaut`) and async (`AsyncCachetronaut`) clients:
>Note: `Cachetronomer` is the shared base class that encapsulates core caching logic used by both the synchronous and asynchronous cache clients.
| Method                           | Description                                                                                                |
| -------------------------------- | ---------------------------------------------------------------------------------------------------------- |
| `__init__`                       | Construct a new cache client with the given database path and settings.                                    |
| `init_async` (Async client only) | (Async only) Initialize any async-specific internals (e.g. connections).                                   |
| `shutdown`                       | Gracefully stop eviction threads and close the underlying                                                  |
| `set`                            | Store a value under `key` with optional TTL, tags, serializer, etc.                                        |
| `get`                            | Retrieve a cached entry (or `None` if missing/expired), optionally unmarshaled into a Pydantic model.      |
| `delete`                         | Remove the given key from the cache immediately.                                                           |
| `evict`                          | Moves from in-RAM store → cold storage; can also`delete` from storage if expired + logs an eviction event. |
| `store_keys`                     | Return a list of all keys currently persisted in cold storage.                                             |
| `memory_keys`                    | Return a list of all keys currently held in the in-process memory cache.                                   |
| `all_keys`                       | List every key in both memory and                                                                          |
| `key_metadata`                   | Fetch the metadata (TTL, serialization format, tags, version, etc.) for a single cache key.                |
| `store_metadata`                 | Retrieve a list of metadata objects for every entry in the persistent                                      |
| `items`                          | List every item in both memory and                                                                         |
| `evict_all`                      | Evict every entry (logs each eviction) but leaves table structure intact.                                  |
| `clear_all`                      | Delete all entries from both memory and store without logging individually.                                |
| `clear_expired`                  | Purge only those entries whose TTL has elapsed.                                                            |
| `clear_by_tags`                  | Remove entries matching any of the provided tags.                                                          |
| `clear_by_profile`               | Remove all entries that were saved under the given profile name.                                           |
| `memory_stats`                   | Return the top-N hottest keys by in-memory access count.                                                   |
| `store_stats`                    | Return the top-N hottest keys by persisted access count.                                                   |
| `access_logs`                    | Fetch raw access-log rows from SQLite for detailed inspection.                                             |
| `key_access_logs`                | Fetch all access-log entries for a single key.                                                             |
| `clear_access_logs`              | Delete all access-log rows from the database.                                                              |
| `delete_access_logs`             | Delete all access-log rows for the given key.                                                              |
| `eviction_logs`                  | Fetch recent eviction events (manual, TTL, memory-pressure, etc.).                                         |
| `clear_eviction_logs`            | Delete all recorded eviction events.                                                                       |
| `profile` (`@property`)          | Get current Profile.                                                                                       |
| `profile` (`@property.setter`)   | Switch to a named Profile, applying its settings and restarting eviction threads.                          |
| `update_active_profile`          | Modify the active profile’s settings in-place and persist them.                                            |
| `get_profile`                    | Load the settings of a named profile without applying them.                                                |
| `delete_profile`                 | Remove a named profile from the `profiles` table.                                                          |
| `list_profiles`                  | List all saved profiles available in the `profiles` table.                                                 |

# 🔭 Cachetronomy Tables
Here's a breakdown of the **tables and columns** you will have in your `cachetronomy` cache.
### 🗃️ `cache`
Stores serialized cached objects, their TTL metadata, tags, and versioning.

|Column            | Type        | Description                                         |
|------------------| ------------| ----------------------------------------------------|
|`key`             | TEXT (PK 🔑)| Unique cache key                                    |
|`data`            | BLOB        | Serialized value (orjson, msgpack, json)            |
|`fmt`             | TEXT        | Serialization format used                           |
|`expire_at`       | DATETIME    | UTC expiry time.                                    |
|`tags`            | TEXT        | Serialized list of tags (usually JSON or CSV format)|
|`version`         | INTEGER     | Version number for schema evolution/versioning      |
|`saved_by_profile`| TEXT        | Profile name that created or last updated this entry|
### 🧾 `access_log`
Tracks when a key was accessed and how frequently.

| Column                     | Type         | Description                       |
| -------------------------- | ------------ | --------------------------------- |
| `key`                      | TEXT (PK 🔑) | Cache key                         |
| `access_count`             | INTEGER      | Number of times accessed          |
| `last_accessed`            | DATETIME     | Most recent access time           |
| `last_accessed_by_profile` | TEXT         | Profile that made the last access |
### 🚮 `eviction_log`
Tracks key eviction events and their reasons (manual, TTL, memory, tag).

| Column               | Type            | Description                                                 |
| -------------------- | --------------- | ----------------------------------------------------------- |
| `id`                 | INTEGER (PK 🔑) | Autoincrement ID                                            |
| `key`                | TEXT            | Evicted key                                                 |
| `evicted_at`         | DATETIME        | Timestamp of eviction                                       |
| `reason`             | TEXT            | Reason string (`"manual_eviction"`, `"time_eviction"`, etc.)|
| `last_access_count`  | INTEGER         | Final recorded access count before eviction                 |
| `evicted_by_profile` | TEXT            | Name of profile that triggered the eviction                 |
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