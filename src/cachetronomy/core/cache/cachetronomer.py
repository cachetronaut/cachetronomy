import inspect
from functools import wraps
from abc import ABC, abstractmethod
from datetime import timedelta
from typing import Any, Callable, TypeVar, ParamSpec

from pydantic import BaseModel

from cachetronomy.core.utils.key_builder import default_key_builder
from cachetronomy.core.serialization import serialize
from cachetronomy.core.types.profiles import Profile
from cachetronomy.core.types.schemas import (
    CacheEntry,
    CacheMetadata,
    ExpiredEntry,
    AccessLogEntry,
    EvictionLogEntry,
)
from cachetronomy.core.store.protocols import StoreProtocol
from cachetronomy.core.store.memory import MemoryCache
from cachetronomy.core.utils.time_utils import _now

P = ParamSpec("P")
R = TypeVar("R")


class Cachetronomer(ABC):
    def __init__(
        self,
        store: StoreProtocol,
        *,
        max_items_in_memory: int | None,
        default_time_to_live: int | None,
        default_tags: list[str] | None,
    ):
        self.store = store
        self._memory = MemoryCache(
            max_items_in_memory,
            on_evict=self._handle_eviction,
        )
        self.time_to_live = default_time_to_live
        self.tags = default_tags

    def __call__(
        self,
        __fn: Callable[P, R] | None = None,
        *,
        time_to_live: int | None = None,
        tags: list[str] | None = None,
        key_builder: Callable[..., str] | None = None,
    ) -> Callable[P, R] | None:
        def decorate(fn: Callable[P, R]) -> Callable[P, R] | None:
            sig = inspect.signature(fn)

            @wraps(fn)
            def wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
                kb = key_builder or default_key_builder
                key = kb(fn, args, kwargs)
                model = (
                    sig.return_annotation
                    if inspect.isclass(sig.return_annotation)
                    and issubclass(sig.return_annotation, BaseModel)
                    else None
                )
                value = self.get(key, model=model)
                if value is not None:
                    return value
                result = fn(*args, **kwargs)
                self.set(
                    key,
                    result,
                    time_to_live=time_to_live or self.time_to_live,
                    tags=tags or self.tags,
                )
                return result

            wrapper.__signature__ = sig
            wrapper.key_for = lambda *a, **k: (
                (key_builder or default_key_builder)(fn, a, k)
            )
            return wrapper

        return decorate(__fn) if __fn else decorate

    def _handle_eviction(
        self,
        key: str,
        *,
        reason: str | None,
        count: int | None,
        value: Any | None,
    ) -> None:
        pass

    def get(
        self,
        key: str,
        model: type[BaseModel] | None = None,
        promote: bool = True,
    ) -> Any | None:
        pass

    def set(
        self,
        key: str,
        value: Any,
        time_to_live: int | None = None,
        version: int | None = None,
        tags: list[str] | None = None,
        prefer: str | None = None,
    ) -> None:
        ttl = time_to_live or self.time_to_live or 0
        tags = tags or self.tags
        expire_at = _now() + timedelta(seconds=ttl)
        version = version or getattr(
            getattr(value, "__class__", None), "__cache_version__", 1
        )
        payload, fmt = serialize(value, prefer=prefer)
        self._memory.set(key, value)
        self.store.save(key, payload, fmt, expire_at, tags, version)

    def store_stats(self, limit: int = 10) -> list[AccessLogEntry] | None:
        pass

    def memory_stats(self) -> dict[str, int] | None:
        pass

    # ——— Abstract Methods ———

    @abstractmethod
    def evict(self, key: str) -> None:
        pass

    @abstractmethod
    def delete(self, key: str) -> None:
        pass

    @abstractmethod
    def store_keys(
        self,
        tags: list[str] | None = None,
        exact_match: bool = False,
    ) -> list[str] | None:
        pass

    @abstractmethod
    def memory_keys(self) -> list[str] | None:
        pass

    @abstractmethod
    def clear_all(self) -> None:
        pass

    @abstractmethod
    def evict_all(self) -> None:
        pass

    @abstractmethod
    def clear_expired(self) -> list[ExpiredEntry] | None:
        pass

    @abstractmethod
    def clear_by_tags(
        self,
        tags: list[str],
        exact_match: bool = False,
    ) -> list[str] | None:
        pass

    @abstractmethod
    def clear_by_profile(self, profile_name: str) -> list[str] | None:
        pass

    @abstractmethod
    def store_metadata(self) -> list[CacheMetadata] | None:
        pass

    @abstractmethod
    def items(self) -> list[CacheEntry] | None:
        pass

    @abstractmethod
    def access_logs(self) -> list[AccessLogEntry] | None:
        pass

    @abstractmethod
    def key_access_logs(self, key: str) -> AccessLogEntry | None:
        pass

    @abstractmethod
    def clear_access_logs(self) -> None:
        pass

    @abstractmethod
    def delete_access_logs(self, key: str) -> AccessLogEntry | None:
        pass

    @abstractmethod
    def get_profile(self, name: str) -> Profile | None:
        pass

    @abstractmethod
    def list_profiles(self) -> list[Profile] | None:
        pass

    @abstractmethod
    def delete_profile(self, name: str) -> None:
        pass

    @abstractmethod
    def eviction_logs(
        self,
        limit: int | None = 1000,
    ) -> list[EvictionLogEntry] | None:
        pass

    @abstractmethod
    def shutdown(self) -> None:
        pass