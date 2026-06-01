'''
Cachetronomy package.

Provides synchronous and asynchronous cache client for easy integration.
'''
from importlib.metadata import PackageNotFoundError, version as _pkg_version

try:
    # uvloop is an optional accelerator. It has no wheels on some platforms
    # (e.g. Windows), so guard the import to keep `import cachetronomy` working
    # everywhere and fall back to the default asyncio event loop. Set the policy
    # directly rather than via the (deprecated) ``uvloop.install()`` helper.
    import asyncio

    import uvloop

    asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
except Exception:  # pragma: no cover - falls back to the stdlib event loop
    pass

from cachetronomy.core.cache.cachetronaut import Cachetronaut  # noqa: E402
from cachetronomy.core.types.profiles import Profile # noqa: E402

try:
    __version__ = _pkg_version('cachetronomy')
except PackageNotFoundError:  # pragma: no cover - source checkout without install
    __version__ = '0.0.0'

__all__ = ['Cachetronaut', 'Profile', '__version__']