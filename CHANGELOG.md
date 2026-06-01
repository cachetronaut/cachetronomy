# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and this project adheres
to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.4.0]

### Fixed
- **Expired entries are no longer served.** `get()` returned stale data after
  deleting an expired entry in non-CLI mode; it now returns the `default`.
- **In-memory `max_items` eviction now works.** The cap was bypassed because the
  async eviction coroutine was never awaited, and the active profile's
  `max_items_in_memory` was never propagated to the in-memory store.
- **In-memory entries now respect TTL.** A still-resident expired entry is
  treated as a miss instead of being served stale.
- **Pydantic results from the persistent store no longer raise.** `get()` passed
  the model positionally to `deserialize()`, whose `model_type` is keyword-only.
- **The `@cache` decorator works on a freshly-constructed client** (previously
  raised `AttributeError: time_to_live` before any profile was applied).
- `clear_by_tags` no longer re-runs the same delete once per matched key.
- `delete_many` returns the number of keys that actually existed, not the input
  length.
- `import cachetronomy` no longer hard-fails where uvloop has no wheels
  (e.g. Windows); the accelerator is now optional and guarded.
- `serialization`'s msgpack loader round-trips `str` input via `latin-1`.
- Removed deprecation/portability warnings (`uvloop.install()`, an un-awaited
  `BatchLogger` coroutine) and a Python 3.13-only import in `protocols.py`.

### Added
- **`None` is now cacheable.** `get()` gained a `default` parameter; pass a
  sentinel to distinguish a genuine miss from a cached `None`. The decorator,
  `get_many`, and `get_or_compute` use this internally.
- `health_check()` reports a real `degraded` status under memory pressure and
  uses an efficient `COUNT(*)` instead of fetching all keys.
- `cachetronomy.__version__`.
- GitHub Actions CI (pytest matrix on 3.10–3.13 + ruff).
- `AGENTS.md` contributor guide and a regression test suite.

### Changed
- `get_or_compute` is documented as a read-through helper; it does **not**
  provide cache-stampede protection (the previous docs over-claimed this).
