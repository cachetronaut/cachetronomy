import inspect
from typing import Callable


def default_key_builder(fn: Callable, args, kwargs) -> str:
    sig = inspect.signature(fn)
    bound = sig.bind_partial(*args, **kwargs)
    parts = [f'{name}={value!r}' for name, value in bound.arguments.items()]
    human_readable = ', '.join(parts)
    return f'{fn.__name__}({human_readable})'
