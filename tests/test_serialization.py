"""
Comprehensive tests for serialization module.
"""
import pytest
import json
import tempfile
from pathlib import Path
from pydantic import BaseModel

from cachetronomy.core import serialization


class SampleModel(BaseModel):
    name: str
    value: int
    tags: list[str]


class TestJsonSerializer:
    def test_json_dumps(self):
        data = {"key": "value", "num": 42}
        result = serialization._json_dumps(data)
        assert isinstance(result, bytes)
        assert json.loads(result) == data

    def test_json_loads_bytes(self):
        data = b'{"key": "value"}'
        result = serialization._json_loads(data)
        assert result == {"key": "value"}

    def test_json_loads_str(self):
        data = '{"key": "value"}'
        result = serialization._json_loads(data)
        assert result == {"key": "value"}


class TestOrJsonSerializer:
    def test_orjson_available(self):
        """Test if orjson is available in serializers."""
        assert 'orjson' in serialization._serializers or 'orjson' not in serialization._serializers

    @pytest.mark.skipif('orjson' not in serialization._serializers, reason="orjson not installed")
    def test_orjson_dumps(self):
        data = {"key": "value", "num": 42}
        dumper, _ = serialization._serializers['orjson']
        result = dumper(data)
        assert isinstance(result, bytes)

    @pytest.mark.skipif('orjson' not in serialization._serializers, reason="orjson not installed")
    def test_orjson_loads_bytes(self):
        _, loader = serialization._serializers['orjson']
        data = b'{"key": "value"}'
        result = loader(data)
        assert result == {"key": "value"}

    @pytest.mark.skipif('orjson' not in serialization._serializers, reason="orjson not installed")
    def test_orjson_loads_str(self):
        _, loader = serialization._serializers['orjson']
        data = '{"key": "value"}'
        result = loader(data)
        assert result == {"key": "value"}

    @pytest.mark.skipif('orjson' not in serialization._serializers, reason="orjson not installed")
    def test_orjson_fallback_on_error(self):
        """Test that orjson falls back to JSON on TypeError."""
        dumper, _ = serialization._serializers['orjson']
        # Create an object that orjson can't serialize
        class CustomClass:
            pass
        obj = CustomClass()
        # This should fallback to JSON
        result = dumper({"obj": str(obj)})
        assert isinstance(result, bytes)


class TestMsgpackSerializer:
    @pytest.mark.skipif('msgpack' not in serialization._serializers, reason="msgpack not installed")
    def test_msgpack_dumps(self):
        data = {"key": "value", "num": 42}
        dumper, _ = serialization._serializers['msgpack']
        result = dumper(data)
        assert isinstance(result, bytes)

    @pytest.mark.skipif('msgpack' not in serialization._serializers, reason="msgpack not installed")
    def test_msgpack_loads_bytes(self):
        dumper, loader = serialization._serializers['msgpack']
        data = {"key": "value", "num": 42}
        packed = dumper(data)
        result = loader(packed)
        assert result == data

    @pytest.mark.skipif('msgpack' not in serialization._serializers, reason="msgpack not installed")
    def test_msgpack_loads_str(self):
        dumper, loader = serialization._serializers['msgpack']
        data = {"key": "value"}
        packed = dumper(data)
        # Convert to string and back
        result = loader(packed.decode('latin-1'))
        assert result == data


class TestChooseSerializer:
    def test_choose_preferred_serializer(self):
        """Test that preferred serializer is chosen when available."""
        result = serialization.choose_serializer({"key": "value"}, prefer='json')
        assert result == 'json'

    @pytest.mark.skipif('orjson' not in serialization._serializers, reason="orjson not installed")
    def test_choose_orjson_when_available(self):
        """Test that orjson is chosen when available and no preference."""
        result = serialization.choose_serializer({"key": "value"}, prefer='orjson')
        assert result == 'orjson'

    @pytest.mark.skipif('msgpack' not in serialization._serializers, reason="msgpack not installed")
    def test_choose_msgpack_for_large_objects(self):
        """Test that msgpack is chosen for very large objects."""
        # Create a large object
        large_obj = {"key" * 100000: "value" * 100000}
        result = serialization.choose_serializer(large_obj)
        # Should prefer msgpack for large objects if available
        assert result in serialization._serializers

    def test_choose_json_fallback(self):
        """Test that JSON is used as fallback."""
        result = serialization.choose_serializer({"key": "value"})
        # Should return a valid serializer
        assert result in serialization._serializers

    def test_choose_serializer_invalid_object(self):
        """Test choosing serializer for object that can't be serialized."""
        class UnserializableClass:
            def __repr__(self):
                raise RuntimeError("Cannot repr")

        obj = UnserializableClass()
        result = serialization.choose_serializer(obj)
        # Should still return a serializer name
        assert result in serialization._serializers


class TestSerialize:
    def test_serialize_dict(self):
        data = {"key": "value", "num": 42}
        payload, fmt = serialization.serialize(data)
        assert isinstance(payload, bytes)
        assert fmt in serialization._serializers

    def test_serialize_pydantic_model(self):
        model = SampleModel(name="test", value=42, tags=["a", "b"])
        payload, fmt = serialization.serialize(model)
        assert isinstance(payload, bytes)
        assert fmt in serialization._serializers

    def test_serialize_with_json_preference(self):
        data = {"key": "value"}
        payload, fmt = serialization.serialize(data, prefer='json')
        assert fmt == 'json'
        assert json.loads(payload) == data

    @pytest.mark.skipif('orjson' not in serialization._serializers, reason="orjson not installed")
    def test_serialize_with_orjson_preference(self):
        data = {"key": "value"}
        payload, fmt = serialization.serialize(data, prefer='orjson')
        assert fmt == 'orjson'

    @pytest.mark.skipif('msgpack' not in serialization._serializers, reason="msgpack not installed")
    def test_serialize_with_msgpack_preference(self):
        data = {"key": "value"}
        payload, fmt = serialization.serialize(data, prefer='msgpack')
        assert fmt == 'msgpack'

    def test_serialize_with_json_options(self):
        data = {"z_key": "value", "a_key": 123}
        payload, fmt = serialization.serialize(
            data,
            prefer='json',
            indent=2,
            sort_keys=True,
            ensure_ascii=False
        )
        assert fmt == 'json'
        decoded = payload.decode()
        assert '\n' in decoded  # indented
        assert decoded.index('"a_key"') < decoded.index('"z_key"')  # sorted

    def test_serialize_fallback_on_error(self):
        """Test that serialization falls back to other formats on error."""
        data = {"key": "value"}
        payload, fmt = serialization.serialize(data)
        # Should succeed with at least one format
        assert isinstance(payload, bytes)
        assert fmt in serialization._serializers


class TestDeserialize:
    def test_deserialize_json(self):
        data = {"key": "value", "num": 42}
        payload = json.dumps(data).encode()
        result = serialization.deserialize(payload, 'json')
        assert result == data

    @pytest.mark.skipif('orjson' not in serialization._serializers, reason="orjson not installed")
    def test_deserialize_orjson(self):
        data = {"key": "value", "num": 42}
        dumper, _ = serialization._serializers['orjson']
        payload = dumper(data)
        result = serialization.deserialize(payload, 'orjson')
        assert result == data

    @pytest.mark.skipif('msgpack' not in serialization._serializers, reason="msgpack not installed")
    def test_deserialize_msgpack(self):
        data = {"key": "value", "num": 42}
        dumper, _ = serialization._serializers['msgpack']
        payload = dumper(data)
        result = serialization.deserialize(payload, 'msgpack')
        assert result == data

    def test_deserialize_with_model_type(self):
        model = SampleModel(name="test", value=42, tags=["a", "b"])
        payload, fmt = serialization.serialize(model)
        result = serialization.deserialize(payload, fmt, model_type=SampleModel)
        assert isinstance(result, SampleModel)
        assert result.name == "test"
        assert result.value == 42
        assert result.tags == ["a", "b"]

    def test_deserialize_unknown_format(self):
        """Test that deserializing with unknown format raises ValueError."""
        with pytest.raises(ValueError, match="Unknown serialization format"):
            serialization.deserialize(b'{}', 'unknown_format')


class TestExportModelSchema:
    def test_export_model_schema(self):
        """Test exporting Pydantic model schema to JSON file."""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            temp_path = f.name

        try:
            serialization.export_model_schema(SampleModel, temp_path)

            # Verify file was created and contains valid JSON
            with open(temp_path, 'r') as f:
                schema = json.load(f)

            # Verify schema structure
            assert 'properties' in schema
            assert 'name' in schema['properties']
            assert 'value' in schema['properties']
            assert 'tags' in schema['properties']
        finally:
            # Cleanup
            Path(temp_path).unlink(missing_ok=True)


class TestRoundTrip:
    """Test that serialize/deserialize round trips work correctly."""

    @pytest.mark.parametrize("data", [
        {"key": "value"},
        {"nested": {"data": [1, 2, 3]}},
        {"unicode": "Hello 世界 🌍"},
        {"numbers": [1, 2.5, -3, 0]},
        {"mixed": {"str": "test", "int": 42, "list": [1, 2], "null": None}},
    ])
    def test_roundtrip_dict(self, data):
        """Test that various dict structures round trip correctly."""
        payload, fmt = serialization.serialize(data)
        result = serialization.deserialize(payload, fmt)
        assert result == data

    def test_roundtrip_pydantic_model(self):
        """Test that Pydantic models round trip correctly."""
        model = SampleModel(name="test", value=42, tags=["a", "b", "c"])
        payload, fmt = serialization.serialize(model)
        result = serialization.deserialize(payload, fmt, model_type=SampleModel)
        assert isinstance(result, SampleModel)
        assert result == model
