# AGENTS.md

Working notes for humans and AI agents contributing to **Cachetronomy**.

## What this is

A lightweight, SQLite-backed cache for Python with first-class sync **and** async
support via [synchronaut](https://github.com/cachetronaut/synchronaut). One
`Cachetronaut` client serves both calling styles; methods decorated with
`@synchronaut()` can be awaited *or* called synchronously.

## Layout — where things live

```
src/cachetronomy/
  __init__.py                 # public exports: Cachetronaut, Profile, __version__
  __main__.py                 # Typer CLI (entry point `cachetronomy`)
  core/
    cache/cachetronaut.py     # the client: decorator, cache API, bulk ops, stats
    store/
      memory.py               # in-process LRU/LFU MemoryCache (+ MISS sentinel)
      sqlite/synchronous.py   # SQLiteStore: the persistent backend (schema lives here)
      utils/batch_logger.py   # batched access/eviction log writer
      utils/sanitizers.py     # row -> dict tag cleaning
      protocols.py            # deprecated/unused store Protocols (kept for reference)
    eviction/
      time_to_live.py         # TTLEvictionThread
      memory.py               # MemoryEvictionThread (RAM-pressure based)
    types/
      schemas.py              # Pydantic models (CacheEntry, *LogEntry, CustomQuery, ...)
      profiles.py             # Profile model + YAML loader
      settings.py             # CacheSettings (env-driven, CACHE_ prefix)
    serialization.py          # pluggable (json / orjson / msgpack) serialize/deserialize
    access_frequency.py       # global hot-key counter
    utils/{key_builder,time_utils}.py
tests/                        # pytest; see conftest.py for fixtures/dummies
examples/                     # runnable usage examples (keep these working!)
```

## Conventions

- **Sync/async bridge:** public client/store methods are `@synchronaut()`. Never
  create an un-awaited coroutine. When bridging from a sync context use
  synchronaut's `call_any`; when scheduling work onto a possibly-running loop
  from another thread, use `asyncio.run_coroutine_threadsafe`.
- **Times are UTC.** Always use `core.utils.time_utils._now()`; never call
  `datetime.now()` directly.
- **Misses use the `MISS` sentinel**, not `None` — `None` is a cacheable value.
  Public `get()` returns its `default` (None) on a miss; internal callers pass
  `default=MISS` to distinguish.
- **Schema is owned by `SQLiteStore`.** Table/index DDL and migrations belong in
  `store/sqlite/synchronous.py`.
- **Profiles drive runtime settings.** Applying a profile must keep derived
  attributes (incl. `self._memory.max_items`) in sync.
- **Serialization is pluggable;** new formats register into
  `serialization._serializers`. Keep the `serialize()` fallback order stable.
- Match surrounding style (4-space indent, single quotes, type hints). Run
  `ruff` before committing.

## Tests

```bash
uv run --extra fast --extra dev python -m pytest -q   # full suite
uv run --extra lint ruff check src                    # lint
```

- The suite must stay green and warning-free.
- Some fixtures are hand-written doubles (`tests/conftest.py`,
  `test_functional_end_to_end_caching.py`). If you change a `MemoryCache` /
  store contract, update the matching double.
- Keep the files under `examples/` runnable — they are user-facing docs.

## Gotchas

- `import cachetronomy` installs the uvloop policy when available; the import is
  guarded so it degrades gracefully where uvloop has no wheels (e.g. Windows).
- The DB path defaults to the nearest project root (`.git`/`pyproject.toml`) —
  pass `db_path=` explicitly in tests and examples.
- `BatchLogger`'s periodic flush only runs under a genuinely running loop;
  otherwise data is flushed on log-overflow, on `stats()`, and on `stop()`.
