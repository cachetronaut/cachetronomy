# Cachetronomy
A lightweight, SQLite-backed cache for Python with first-class sync **and** async support. Features TTL and memory-pressure eviction, persistent hot-key tracking, pluggable serialization, a decorator API and a CLI.

[![Package Version](https://img.shields.io/pypi/v/cachetronomy.svg)](https://pypi.org/project/cachetronomy/) | [![Supported Python Versions](https://img.shields.io/badge/Python->=3.10-blue?logo=python&logoColor=white)](https://pypi.org/project/cachetronomy/) | [![PyPI Downloads](https://static.pepy.tech/badge/cachetronomy)](https://pepy.tech/projects/cachetronomy) | ![License](https://img.shields.io/github/license/cachetronaut/cachetronomy) | ![GitHub Last Commit](https://img.shields.io/github/last-commit/cachetronaut/cachetronomy)  | ![Status](https://img.shields.io/pypi/status/cachetronomy) | [![Dynamic TOML Badge](https://img.shields.io/badge/dynamic/toml?url=https%3A%2F%2Fraw.githubusercontent.com%2Fcachetronaut%2Fcachetronomy%2Frefs%2Fheads%2Fmain%2Fpyproject.toml&query=project.version&prefix=v&style=flat&logo=github&logoColor=8338EC&label=cachetronomy&labelColor=silver&color=8338EC)](https://github.com/cachetronaut/cachetronomy)

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

The same `Cachetronaut` client works in both sync and async code — call its methods directly or `await` them. See the [`examples/`](examples/) directory for fuller, runnable demos.

```python
from cachetronomy import Cachetronaut

cache = Cachetronaut(db_path='cachetronomy.db')

# Basic set / get — values persist across restarts.
cache.set('user:1', {'name': 'Alice'}, time_to_live=300)
cache.get('user:1')        # {'name': 'Alice'}
cache.get('missing')       # None

# Memoize any function with the decorator. The key is built from the
# function name and its arguments; the return value is cached automatically.
@cache(time_to_live=900)
def expensive(n: int) -> int:
    return sum(range(n))

expensive(1_000_000)       # computed once, then served from cache

cache.shutdown()
```

The decorator works on coroutines too:

```python
import asyncio
from cachetronomy import Cachetronaut

cache = Cachetronaut(db_path='cachetronomy.db')

@cache(time_to_live=60)
async def fetch_user(user_id: int) -> dict:
    await asyncio.sleep(0.5)            # simulate I/O
    return {'id': user_id, 'name': 'Ash'}

async def main():
    await fetch_user(1)                # miss → runs the coroutine
    await fetch_user(1)                # hit  → returned from cache
    await cache.shutdown()

asyncio.run(main())
```

`None` is a real cached value, not a miss. Pass a sentinel as `default` to tell them apart:

```python
MISS = object()
cache.set('maybe', None, time_to_live=60)
cache.get('maybe')                     # None  (cached value)
cache.get('maybe', default=MISS)       # None  (a hit)
cache.get('absent', default=MISS)      # MISS  (a genuine miss)
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
- `get_or_compute` - Use Python API for read-through caching

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

## API Reference
> **Note:** Each `cachetronomy` CLI invocation is a fresh, stateless process, so in-memory features (hot-key tracking, memory-pressure eviction, etc.) aren’t available. All persistent, “cold-storage” operations (get/set against the SQLite store, TTL cleanup, access-log and eviction-log reporting, profiles, etc.) still work as expected.

| Method                         | Description                                                                                                |
| ------------------------------ | ---------------------------------------------------------------------------------------------------------- |
| `__init__`                     | Construct a new cache client with the given database path and settings.                                    |
| `shutdown`                     | Gracefully stop eviction threads and close the underlying database connection.                             |
| `set`                          | Store a value under `key` with optional TTL, tags, serializer, etc.                                        |
| `get`                          | Retrieve a cached entry, optionally unmarshaled into a Pydantic model. Returns `default` (`None`) on a miss; pass a sentinel as `default` to tell a real miss apart from a cached `None`. |
| `delete`                       | Remove the given key from the cache immediately.                                                           |
| `get_many`                     | Retrieve multiple keys at once, returning a dict of key-value pairs.                                       |
| `set_many`                     | Store multiple key-value pairs at once with optional TTL and tags.                                         |
| `delete_many`                  | Delete multiple keys at once, returning the count of keys that existed.                                    |
| `health_check`                 | Perform a health check, returning system status (`healthy`/`degraded`/`unhealthy`, db accessible, memory ok, key counts). |
| `stats`                        | Get comprehensive cache statistics (total keys, hot keys, evictions, profile info).                        |
| `get_or_compute`               | Read-through helper: get a value from cache, or compute and cache it on a miss. (Does not provide stampede protection.) |
| `evict`                        | Remove a key from the in-memory cache without deleting it from the persistent store.                       |
| `store_keys`                   | Return a list of all keys currently persisted in cold storage.                                             |
| `memory_keys`                  | Return a list of all keys currently held in the in-process memory cache.                                   |
| `all_keys`                     | List every key across both memory and the persistent store.                                                |
| `key_metadata`                 | Fetch the metadata (TTL, serialization format, tags, version, etc.) for a single cache key.                |
| `store_metadata`               | Retrieve a list of metadata objects for every entry in the persistent store.                               |
| `items`                        | List every cached item in the persistent store.                                                            |
| `evict_all`                    | Evict every entry from memory (logs each eviction) but leaves the store intact.                            |
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

## Database Schema

### `cache` Table
Stores serialized cached objects, their TTL metadata, tags, and versioning.

|Column            | Type        | Description                                         |
|------------------| ------------| ----------------------------------------------------|
|`key`             | TEXT (PK 🔑)| Unique cache key                                    |
|`data`            | BLOB        | Serialized value (orjson, msgpack, json)            |
|`fmt`             | TEXT        | Serialization format used                           |
|`expire_at`       | DATETIME    | UTC expiry time.                                    |
|`tags`            | TEXT        | Serialized list of tags (JSON)                      |
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
uv run --extra fast --extra dev python -m pytest -q   # run the test suite
uv run --extra lint ruff check src                    # lint
```
There is **100% parity** between sync and async clients via [synchronaut](https://github.com/cachetronaut/synchronaut); coverage includes TTL, memory eviction, decorator api, profiles, serialization and logging.

## Contributing
1. Fork & branch
2. Add tests for new features
3. Submit a PR

See [AGENTS.md](AGENTS.md) for repository conventions.

## License
MIT — see [LICENSE](https://github.com/cachetronaut/cachetronomy/blob/main/LICENSE) for details.
