# Repository Guidelines

## Project Structure & Module Organization
- `src/cachetronomy/` holds the package; public exports (`Cachetronaut`, `Profile`, `__version__`) live in `__init__.py` and the Typer CLI in `__main__.py`.
- `core/cache/cachetronaut.py` is the client (decorator, cache API, bulk ops, stats); `core/store/` holds the in-memory cache (`memory.py`), the SQLite backend and schema (`sqlite/synchronous.py`), and log/serialization utils.
- `core/eviction/` has the TTL and memory-pressure threads; `core/types/` has Pydantic schemas, profiles, and settings; `core/serialization.py` is the pluggable JSON/orjson/msgpack layer.
- `tests/` is pytest (see `conftest.py` for fixtures and hand-written doubles); `examples/` holds runnable usage docs. Place new code in the matching module.

## Build, Test, and Development Commands
- Use `uv` for adding, installing, and executing Python; prefer a tool's CLI through `uv run`.
- `uv run --extra fast --extra dev python -m pytest -q` — full test suite.
- `uv run --extra lint ruff check src` — lint; `ruff format` to format and `ruff check --fix` to resolve violations.
- Use `ty check` for type errors when available.
- `uv lock` after dependency or version changes; `uv build` produces the publishable `dist/` artifacts.

## Coding Style & Naming Conventions
- 4-space indent, single quotes, type hints throughout; match surrounding style and keep changes surgical.
- Write short docstrings only when behavior isn't obvious; avoid single-letter names, prefer explicit pairs like `key` and `value`.
- Public client/store methods are `@synchronaut()` so they work sync or async — never leave a coroutine un-awaited; bridge from sync with `call_any`, schedule onto a running loop from another thread with `asyncio.run_coroutine_threadsafe`.
- Times are UTC: always use `core.utils.time_utils._now()`, never `datetime.now()`.
- Misses use the `MISS` sentinel, not `None` (`None` is a cacheable value); public `get()` returns its `default` on a miss while internal callers pass `default=MISS`.
- Schema/DDL belongs in `store/sqlite/synchronous.py`; applying a profile must keep derived attributes (including `self._memory.max_items`) in sync; new serializers register into `serialization._serializers` and keep the fallback order stable.

## Documentation & Examples
- Keep `examples/*.py` runnable — they are user-facing docs; pass `db_path=` explicitly so they don't write to a project-root default.
- Update `README.md` and `CHANGELOG.md` alongside user-visible changes; use concise, sentence-case prose and repository-relative paths.

## Commit & Pull Request Guidelines
- Prefer short, imperative subjects (e.g. `Fix expired entries served from store`); expand detail in the body when needed.
- Keep each commit scoped to one logical change; do not add a co-author trailer (match existing history).
- PRs should state in plain English why they exist, summarize the changes and their impact, and list verification steps.

## Release Guidelines
- Versioning is SemVer; bump `pyproject.toml`, then sync `uv.lock` so the editable `cachetronomy` entry matches.
- Backward-compatible features bump the minor; fixes bump the patch; record every release in `CHANGELOG.md`.
- Publish to PyPI from `dist/` (`uv build` then `uv publish`); keep `pyproject.toml`, `uv.lock`, the git tag (`vX.Y.Z`), and the PyPI version in sync.

## Security & Configuration Tips
- Do not commit `.env`, secrets, or local `*.db` artifacts; the default DB path resolves to the nearest project root, so pass `db_path=` in tests and examples.
- `import cachetronomy` installs the uvloop policy when available; the import is guarded so it degrades gracefully where uvloop has no wheels (e.g. Windows).

## Verification Guidelines
- Tests are behavioral: assert expected outputs for given inputs, and name them after observable behavior (e.g. `test_expired_store_entry_not_served`).
- New behavior should include targeted regression tests; if you change a `MemoryCache` or store contract, update the matching test double.
- The suite must stay green and warning-free; run `ruff check src` and the full `pytest` run for any area touched, and report anything that could not be run.
