'''
Cachetronomy package.

Provides synchronous and asynchronous cache client for easy integration.
'''
import uvloop
uvloop.install() 

from cachetronomy.core.cache.cachetronaut import Cachetronaut  # noqa: E402
from cachetronomy.core.types.profiles import Profile # noqa: E402

__all__ = ['Cachetronaut', 'Profile']