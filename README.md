# Cachetronomy
A lightweight, SQLite-backed cache for Python with first-class sync **and** async support. Features TTL and memory-pressure eviction, persistent hot-key tracking, pluggable serialization, a decorator API and a CLI.

[![Package Version](https://img.shields.io/pypi/v/cachetronomy.svg)](https://pypi.org/project/cachetronomy/) | [![Supported Python Versions](https://img.shields.io/badge/Python->=3.9-blue?logo=python&logoColor=white)](https://pypi.org/project/cachetronomy/) | [![PyPI Downloads](https://static.pepy.tech/badge/cachetronomy)](https://pepy.tech/projects/cachetronomy) | ![License](https://img.shields.io/github/license/cachetronaut/cachetronomy) | ![GitHub Last Commit](https://img.shields.io/github/last-commit/cachetronaut/cachetronomy)  | ![Status](https://img.shields.io/pypi/status/cachetronomy) | [![Dynamic TOML Badge](https://img.shields.io/badge/dynamic/toml?url=https%3A%2F%2Fraw.githubusercontent.com%2Fcachetronaut%2Fcachetronomy%2Frefs%2Fheads%2Fmain%2Fpyproject.toml&query=project.version&prefix=v&style=flat&logo=github&logoColor=8338EC&label=cachetronomy&labelColor=silver&color=8338EC)](https://github.com/cachetronaut/cachetronomy)

## Why Cachetronomy?
- **Persistent**: stores entries in SQLite; survives restarts—no external server.  
- **Unified API**: one `Cachetronaut` class handles both sync and async calls via [synchronaut](https://github.com/cachetronaut/synchronaut).  
- **Smart Eviction**: TTL expiry and RAM-pressure eviction run in background tasks.  
- **Hot-Key Tracking**: logs every read in memory & SQLite; query top-N hotspots.  
- **Flexible Serialization**: JSON, orjson, MsgPack out-of-the-box; swap in your own.  
- **Decorator API**: wrap any function or coroutine to cache its results automatically.  
- **CLI**: full-featured command-line interface for inspection and maintenance.

## Installation
```bash
pip install cachetronomy
# for orjson & msgpack support:
pip install cachetronomy[fast]
```
## Quick Start

**Note**: For simpler examples, see the `examples/` directory. The example below demonstrates core features with creative flair.
```python
import asyncio
import random
import time

from typing import Any, Dict
from itertools import cycle
from rich.console import Console
from rich.pretty import pprint # pretty indeed!

from cachetronomy import Cachetronaut # imports the client that can be used in both sync and async contexts 


console = Console()

QUOTES_DB = {
    'Cache Me If You Can': [
        'Eluding garbage collection like a phantom of the heap.',
        'You can check out any time you like, but you can never evict!',
        'I’ll be back—just as soon as I reload you into memory.'
    ],
    'Cacheablanca': [
        'Of all the cache in all the memory, she walked into mine.',
        'Here’s looking at you, hot entry.',
        'Play it again, cache.'
    ],
    'Cache of the Titans': [
        'In the war of the in-memory gods, latency is your enemy.',
        'Welcome to the arena—only the hottest entries survive.',
        'Clash of the Titans? More like clash of the Caches.'
    ],
    'The Quick and the Cached': [
        'Draw first… or spend eternity waiting on disk I/O.',
        'Fastest hit in the West: make your move.',
        'Fill ‘er up—with cache hits!'
    ],
}

CELEBRITIES = [
    'Ash Cache-um',
    'Buzz Cacheyear',
    'Cachelita Rivera',
    'Captain Jean-Luc Cacheard',
    'Cacheius Clay',
    'Cacheanova',
    'Cache Gordon',
    'Cacheel O’Neal',
    'Cacheper The Friendly Ghost',
    'Samuel L. Cacheson',
    'Cache Thoreau',
    'Cache Timbers',
    'Jonny Cache',
    'Neil deCache Tyson',
    'The Cachelor',
    'The Cachelorian',
]

CELEB_KNOWN = {
    'Ash Cache-um': 'Trying to cache ’em all',
    'Buzz Cacheyear': 'To infinity and... hold on, let me fetch that',
    'Cachelita Rivera': 'Singing to the tune of in-memory persistence',
    'Captain Jean-Luc Cacheard': 'Boldly caching where no request has gone before.',
    'Cacheius Clay': 'Float like a butterfly, store like a RAM',
    'Cacheanova': 'Seducing data into staying just a little longer',
    'Cache Gordon': 'Defender of the memoryverse',
    'Cacheel O’Neal': 'Slams every request through the L2 backboard.',
    'Cacheper The Friendly Ghost': 'Cacheually haunting unset TTLs for eternity.',
    'Samuel L. Cacheson': 'Dropping eviction bombs on stale entries and unleashing badass cache hits',
    'Cache Thoreau': 'Moves to Walden Pond where cold storage can’t find him.',
    'Cache Timbers': 'Pirates cry his name when the hit-ratio drops: “CACHE THE TIMBERS!”',
    'Jonny Cache': 'Serving time for exceeding the Folsom’s TTL',
    'Neil deCache Tyson': 'Famous Cachetro-Physicist',
    'The Cachelor': 'Hands out roses... and TTLs',
    'The Cachelorian': 'Keeper of ancient cache tech',
}

def sync_main():
    console.print('\n# ––– Sync Client Test –––')
    cachetronaut = Cachetronaut(db_path='cachetronomy.db')
    cachetronaut.clear_all()

    # Confirm cache is empty at start
    console.print(
        '[cornflower_blue]Initial items:', 
        f'{[entry.model_dump() for entry in cachetronaut.items()]}'
    )

    @cachetronaut(time_to_live=900, prefer='json')
    def pull_quote(celebrity: str, film: str) -> str:
        '''Simulate an expensive lookup by picking a random film quote.'''
        time.sleep(2)  # simulate latency
        return random.choice(QUOTES_DB[film])

    # Cycle through films so every celebrity gets a turn
    films = list(QUOTES_DB.keys())
    combos = list(zip(CELEBRITIES, cycle(films)))

    for celebrity, film in combos:
        known_for = CELEB_KNOWN[celebrity]
        console.print(
            f'\n→ [blue]{celebrity!r}[/blue],',
            f' known for [blue]{known_for!r}[/blue],',
            f' is requesting quote from [blue]{film!r}[/blue]'
        )

        # First call: cache miss
        t0 = time.time()
        quote1 = pull_quote(celebrity, film)
        console.print(f'\t→ [red](miss) {quote1!r}  ({time.time() - t0:.2f}s)')

        # Second call: cache hit (fast)
        t1 = time.time()
        quote2 = pull_quote(celebrity, film)
        console.print(f'\t→ [green](hit) {quote2!r}  ({time.time() - t1:.2f}s)')

        # Ensure memoization
        assert quote1 == quote2, 'Cache returned a different quote!'

    # Demonstrate manual eviction
    sample_celebrity, sample_film = combos[0]
    sample_key = f"pull_quote(celebrity='{sample_celebrity}', film='{sample_film}')"
    console.print('\n[light_goldenrod1]Stored keys:')
    pprint(cachetronaut.store_keys())
    console.print(f'\n[bright_red]Evicting key:[/bright_red] {sample_key}')
    cachetronaut.evict(sample_key)
    cachetronaut.clear_expired()
    result = cachetronaut.get(sample_key)
    console.print('\n[blue_violet]After eviction, get() →')
    pprint(result)

# OR TRY IT ASYNC

async def async_main():
    console.print('\n# ––– Async Client Test –––')

    # 1. Init your async client
    cachetronaut = Cachetronaut(db_path='cachetronomy.db')
    await cachetronaut.clear_all()

    # 2. Decorate your coroutine—cache results for 2 seconds
    @cachetronaut(time_to_live=2, prefer='json')
    async def gotta_cache_em_all(trainer_id: int) -> Dict[str, Any]:
        console.print('[bright_green]Welcome to the wonderful world of Cachémon.')
        await asyncio.sleep(0.5)
        console.print('[bright_red]Pick your starter Cachémon, I\'d start with a 🔥 type.')
        await asyncio.sleep(0.5)
        console.print('[bright_blue]Go get that first gym badge.')
        await asyncio.sleep(0.5)
        console.print('[bright_yellow]Go get the next seven gym badges.')
        await asyncio.sleep(0.5)
        console.print('[bright_cyan]Beat Blue (for the 100th time).')
        await asyncio.sleep(0.5)
        console.print('[bright_white]Also, you are gonna train if you want to get to the E4.')
        await asyncio.sleep(0.5)
        console.print('[bright_magenta]Now you got to beat the E4.')
        await asyncio.sleep(0.5)
        console.print('[gold1]You did it! you are a Cachémon master!')
        return {
            'id': trainer_id,
            'name': 'Ash Cache-um',
            'type': 'Person',
            'known_for': 'Trying to cache ’em al',
            'cachémon': [
                {
                    'name': 'Picacheu',
                    'type': 'cachémon',
                    'ability': 'Shocking retrieval speeds ⚡️'
                },
                {
                    'name': 'Sandcache',
                    'type': 'cachémon',
                    'ability': 'Slashing latency with sharp precision ⚔️'
                },
                {
                    'name': 'Rapicache',
                    'type': 'cachémon',
                    'ability': 'Blazing-fast data delivery 🔥'},
                {
                    'name': 'Cachecoon',
                    'type': 'cachémon',
                    'ability': 'Securely cocooning your valuable data 🐛'
                },
                {
                    'name': 'Cachedform',
                    'type': 'cachémon',
                    'ability': 'Adapting to any data climate ☁️☀️🌧️'
                },
                {
                    'name': 'Cachenea',
                    'type': 'cachémon',
                    'ability': 'Pinpointing the freshest data points 🌵'}
                ,
            ],
            'cachémon_champion': True,
            'cachémon_champion_date': time.ctime(),
        }
    
    # 3. On first call → cache miss, runs the coroutine
    t0 = time.time()
    trainer_one = await gotta_cache_em_all(1301)
    console.print(
        '\ntrainer_one = await gotta_cache_em_all(1301) ↑↑↑\n',
        f'→ [red](miss) `trainer_one` ({time.time() - t0:.2f}s): ↓↓↓'
    )
    pprint(trainer_one)

    # 4. Second call within TTL → cache hit (returns instantly)
    t1 = time.time()
    trainer_two = await gotta_cache_em_all(1301)
    console.print(
        '\ntrainer_two = await gotta_cache_em_all(1301)\n',
        f'→ [green](hit) `trainer_two` ({time.time() - t1:.2f}s): ↓↓↓'
    )
    pprint(trainer_two)

    console.print(f'\n{trainer_one is trainer_two = }')
    console.print(
        '\nawait cachetronaut.get("gotta_cache_em_all(trainer_id=1301)")',
        ' [bright_green](entry=active)[/bright_green] ↓↓↓'
    )
    pprint(await cachetronaut.get('gotta_cache_em_all(trainer_id=1301)'))

    # 5. Test eviction / cleanup
    await asyncio.sleep(2.5) # Let the entry expire
    await cachetronaut.clear_expired()
    console.print(
        '\nawait cachetronaut.get("gotta_cache_em_all(trainer_id=1301)")',
        ' [bright_red](entry=expired)[/bright_red] ↓↓↓'
    )
    pprint(await cachetronaut.get('gotta_cache_em_all(trainer_id=1301)'))

    await cachetronaut.shutdown()

if __name__ == '__main__':
    sync_main()
    asyncio.run(async_main())
```

## CLI Usage

The `cachetronomy` command provides a full-featured CLI for cache inspection and maintenance.

### Basic Commands

```bash
# Get help
cachetronomy --help

# Set a value with TTL
cachetronomy set --time-to-live=300 my-key "my value"

# Get a value
cachetronomy get my-key

# Delete a key
cachetronomy delete my-key

# List all keys
cachetronomy all-keys

# List profiles
cachetronomy list-profiles

# View store statistics
cachetronomy store-stats

# Clear expired entries
cachetronomy clear-expired

# Clear by tags
cachetronomy clear-by-tags --tags='["api"]' --exact-match=false
```

### Common Operations

**Set and retrieve values**:
```bash
# Store with TTL
cachetronomy set --time-to-live=3600 user:1 '{"name": "Alice"}'

# Retrieve
cachetronomy get user:1

# With tags
cachetronomy set --tags='["users", "api"]' user:2 '{"name": "Bob"}'
```

**Profile management**:
```bash
# List available profiles
cachetronomy list-profiles

# Switch profile
cachetronomy set-profile production

# Get current profile
cachetronomy get-profile
```

**Maintenance**:
```bash
# Clear expired entries
cachetronomy clear-expired

# Clear all cache
cachetronomy clear-all

# View access logs
cachetronomy access-logs

# View eviction logs
cachetronomy eviction-logs
```

### Database Path

By default, the CLI uses `cachetronomy.db` in the current directory. Specify a different path:

```bash
cachetronomy --db-path /path/to/cache.db list-profiles
```

### Note on CLI Limitations

Some methods are not available via CLI due to type complexity:
- `get_many`, `set_many`, `delete_many` - Use Python API for bulk operations
- `health_check`, `stats` - Use Python API for monitoring dicts
- `get_or_compute` - Use Python API for stampede protection

These methods remain fully functional in the Python API.

## Core Mechanisms
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
# API Reference
> **Note:** Each `cachetronomy` CLI invocation is a fresh, stateless process, so in-memory features (hot-key tracking, memory-pressure eviction, etc.) aren’t available. All persistent, “cold-storage” operations (get/set against the SQLite store, TTL cleanup, access-log and eviction-log reporting, profiles, etc.) still work as expected.

| Method                         | Description                                                                                                |
| ------------------------------ | ---------------------------------------------------------------------------------------------------------- |
| `__init__`                     | Construct a new cache client with the given database path and settings.                                    |
| `shutdown`                     | Gracefully stop eviction threads and close the underlying                                                  |
| `set`                          | Store a value under `key` with optional TTL, tags, serializer, etc.                                        |
| `get`                          | Retrieve a cached entry (or `None` if missing/expired), optionally unmarshaled into a Pydantic model.      |
| `delete`                       | Remove the given key from the cache immediately.                                                           |
| `get_many`                     | Retrieve multiple keys at once, returning a dict of key-value pairs.                                       |
| `set_many`                     | Store multiple key-value pairs at once with optional TTL and tags.                                         |
| `delete_many`                  | Delete multiple keys at once, returning the count of deleted keys.                                         |
| `health_check`                 | Perform a health check, returning system status (db accessible, memory ok, key counts).                    |
| `stats`                        | Get comprehensive cache statistics (total keys, hot keys, evictions, profile info).                        |
| `get_or_compute`               | Get value from cache or compute it if missing (prevents cache stampede).                                   |
| `evict`                        | Moves from in-RAM store → cold storage; can also`delete` from storage if expired + logs an eviction event. |
| `store_keys`                   | Return a list of all keys currently persisted in cold storage.                                             |
| `memory_keys`                  | Return a list of all keys currently held in the in-process memory cache.                                   |
| `all_keys`                     | List every key in both memory and                                                                          |
| `key_metadata`                 | Fetch the metadata (TTL, serialization format, tags, version, etc.) for a single cache key.                |
| `store_metadata`               | Retrieve a list of metadata objects for every entry in the persistent                                      |
| `items`                        | List every item in both memory and                                                                         |
| `evict_all`                    | Evict every entry (logs each eviction) but leaves table structure intact.                                  |
| `clear_all`                    | Delete all entries from both memory and store without logging individually.                                |
| `clear_expired`                | Purge only those entries whose TTL has elapsed.                                                            |
| `clear_by_tags`                | Remove entries matching any of the provided tags.                                                          |
| `clear_by_profile`             | Remove all entries that were saved under the given profile name.                                           |
| `memory_stats`                 | Return the top-N hottest keys by in-memory access count.                                                   |
| `store_stats`                  | Return the top-N hottest keys by persisted access count.                                                   |
| `access_logs`                  | Fetch raw access-log rows from SQLite for detailed inspection.                                             |
| `key_access_logs`              | Fetch all access-log entries for a single key.                                                             |
| `clear_access_logs`            | Delete all access-log rows from the database.                                                              |
| `delete_access_logs`           | Delete all access-log rows for the given key.                                                              |
| `eviction_logs`                | Fetch recent eviction events (manual, TTL, memory-pressure, etc.).                                         |
| `clear_eviction_logs`          | Delete all recorded eviction events.                                                                       |
| `profile` (`@property`)        | Get current Profile.                                                                                       |
| `set_profile`                  | Switch to a named Profile, applying its settings and restarting eviction threads.                          |
| `update_active_profile`        | Modify the active profile’s settings in-place and persist them.                                            |
| `get_profile`                  | Load the settings of a named profile without applying them.                                                |
| `delete_profile`               | Remove a named profile from the `profiles` table.                                                          |
| `list_profiles`                | List all saved profiles available in the `profiles` table.                                                 |

# Database Schema

## Tables Overview

### `cache` Table
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
### `access_log` Table
Tracks when a key was accessed and how frequently.

| Column                     | Type         | Description                       |
| -------------------------- | ------------ | --------------------------------- |
| `key`                      | TEXT (PK 🔑) | Cache key                         |
| `access_count`             | INTEGER      | Number of times accessed          |
| `last_accessed`            | DATETIME     | Most recent access time           |
| `last_accessed_by_profile` | TEXT         | Profile that made the last access |
### `eviction_log` Table
Tracks key eviction events and their reasons (manual, TTL, memory, tag).

| Column               | Type            | Description                                                 |
| -------------------- | --------------- | ----------------------------------------------------------- |
| `id`                 | INTEGER (PK 🔑) | Autoincrement ID                                            |
| `key`                | TEXT            | Evicted key                                                 |
| `evicted_at`         | DATETIME        | Timestamp of eviction                                       |
| `reason`             | TEXT            | Reason string (`'manual_eviction'`, `'time_eviction'`, etc.)|
| `last_access_count`  | INTEGER         | Final recorded access count before eviction                 |
| `evicted_by_profile` | TEXT            | Name of profile that triggered the eviction                 |
### `profiles` Table
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
## Development & Testing
```bash
git clone https://github.com/cachetronaut/cachetronomy.git
cd cachetronomy
pip install -r requirements-dev.txt
pytest
```
There is **100% parity** between sync and async clients via [synchronaut](https://github.com/cachetronaut/synchronaut); coverage includes TTL, memory eviction, decorator api, profiles, serialization and logging.
## Contributing
1. Fork & branch
2. Add tests for new features
3. Submit a PR
## License
MIT — see [LICENSE](https://github.com/cachetronaut/cachetronomy/blob/main/LICENSE) for details.
