import json
import logging

from typing import Any, Callable
from pydantic import BaseModel


_serializers: dict[
                    str, 
                    tuple[Callable[..., bytes], 
                    Callable[[bytes | str], Any]]
                ] = {}

def _json_dumps(obj: Any, **kwargs) -> bytes:
    return json.dumps(obj, **kwargs).encode()

def _json_loads(data: bytes | str) -> Any:
    if isinstance(data, bytes):
        data = data.decode()
    return json.loads(data)

_serializers['json'] = (_json_dumps, _json_loads)

try:
    import orjson
    def _orjson_dumps(obj: Any, **kwargs) -> bytes:
        try:
            return orjson.dumps(obj)
        except TypeError:
            logging.warning(
                f'orjson failed to serialize {obj!r}; falling back to JSON.'
            )
            return _json_dumps(
                obj,
                sort_keys=kwargs.get('sort_keys', False),
                indent=kwargs.get('indent', None),
                ensure_ascii=kwargs.get('ensure_ascii', False),
            )
    def _orjson_loads(data: bytes | str) -> Any:
        if isinstance(data, bytes):
            return orjson.loads(data)
        return orjson.loads(data.encode())
    _serializers['orjson'] = (_orjson_dumps, _orjson_loads)

except ImportError:
    logging.raiseExceptions(
        'ImportError in `orjson` support; install orjson or omit preference.'
    )
try:
    import msgpack
    def _msgpack_dumps(obj: Any, **kwargs) -> bytes:
        return msgpack.packb(obj, use_bin_type=True)
    def _msgpack_loads(data: bytes | str) -> Any:
        if isinstance(data, str):
            data = data.encode()
        return msgpack.unpackb(data, raw=False)
    _serializers['msgpack'] = (_msgpack_dumps, _msgpack_loads)
except ImportError:
    logging.raiseExceptions(
        'ImportError in `msgpack` support; install msgpack or omit preference.'
    )

def choose_serializer(obj: Any, prefer: str | None = None) -> str:
    if prefer in _serializers:
        logging.debug(f'Preferred serializer "{prefer}" is available.')
        return prefer
    # Test JSON ability
    if 'json' in _serializers:
        try:
            json.dumps(obj)
            return 'json'
        except Exception:
            pass
    # Test msgpack ability
    if 'msgpack' in _serializers:
        try:
            _serializers['msgpack'][0](obj)
            return 'msgpack'
        except Exception:
            pass
    # Large repr heuristic
    try:
        size = len(repr(obj).encode())
    except Exception:
        size = 0
    if size > 1_000_000 and 'msgpack' in _serializers:
        return 'msgpack'
    if 'orjson' in _serializers:
        return 'orjson'
    return 'json'

def serialize(
    obj: Any,
    *,
    prefer: str | None = None,
    indent: int | None = None,
    sort_keys: bool = True,
    ensure_ascii: bool = False
) -> tuple[bytes, str]:
    primitive = obj.model_dump() if isinstance(obj, BaseModel) else obj
    candidates: list[str] = []
    if prefer in _serializers:
        candidates.append(prefer)
    for fmt in ('orjson', 'msgpack', 'json'):
        if fmt in _serializers and fmt not in candidates:
            candidates.append(fmt)
    last_exc: Exception | None = None
    for fmt in candidates:
        dumper, _ = _serializers[fmt]
        try:
            if fmt == 'json':
                payload = dumper(primitive, indent=indent, sort_keys=sort_keys, 
                                 ensure_ascii=ensure_ascii)
            else:
                payload = dumper(primitive)
            logging.debug(f'Serialize: selected format "{fmt}".')
            return payload, fmt
        except Exception as e:
            last_exc = e
            logging.debug(f'Serializer "{fmt}" failed: {e!r}')
    logging.error(
        f'All serializers failed for object {primitive!r}; raising last exception.'
    )
    raise last_exc  

def deserialize(
    data: bytes,
    fmt: str,
    *,
    model_type: BaseModel | None = None
) -> Any:
    if fmt not in _serializers:
        raise ValueError(f'Unknown serialization format {fmt!r}')
    _, loader = _serializers[fmt]
    obj = loader(data)
    if model_type:
        return model_type.model_validate(obj)
    return obj

def export_model_schema(model_cls: BaseModel, out_path: str) -> None:
    schema: dict = model_cls.model_json_schema()
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(schema, f, indent=2, sort_keys=True)
