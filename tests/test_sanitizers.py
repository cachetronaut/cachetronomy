"""
Tests for sanitizers module.
"""
import json
import pytest
from sqlite3 import Row
from cachetronomy.core.store.utils.sanitizers import clean_tags


class FakeRow:
    """Mock sqlite3.Row object for testing."""
    def __init__(self, data: dict):
        self._data = data
        self.keys = lambda: list(data.keys())

    def __getitem__(self, key):
        return self._data[key]

    def __iter__(self):
        return iter(self._data.items())


def test_clean_tags_with_valid_json():
    """Test cleaning tags when tags field contains valid JSON."""
    row = FakeRow({'key': 'test', 'tags': '["tag1", "tag2"]'})
    result = clean_tags(row)
    assert result['tags'] == ["tag1", "tag2"]
    assert result['key'] == 'test'


def test_clean_tags_with_empty_string():
    """Test cleaning tags when tags field is empty string (falsy, not parsed)."""
    row = FakeRow({'key': 'test', 'tags': ''})
    result = clean_tags(row)
    # Empty string is falsy, so if block is skipped
    assert result['tags'] == ''


def test_clean_tags_with_invalid_json():
    """Test cleaning tags when tags field contains invalid JSON."""
    row = FakeRow({'key': 'test', 'tags': 'not json'})
    result = clean_tags(row)
    assert result['tags'] == []


def test_clean_tags_with_none():
    """Test cleaning tags when tags field is None (falsy, not parsed)."""
    row = FakeRow({'key': 'test', 'tags': None})
    result = clean_tags(row)
    # None is falsy, so if block is skipped
    assert result['tags'] is None


def test_clean_tags_with_empty_list():
    """Test cleaning tags when tags is empty list JSON."""
    row = FakeRow({'key': 'test', 'tags': '[]'})
    result = clean_tags(row)
    assert result['tags'] == []


def test_clean_tags_missing_tags_field():
    """Test cleaning tags when tags field is missing (KeyError)."""
    row = FakeRow({'key': 'test'})
    result = clean_tags(row)
    assert result['tags'] == []


def test_clean_tags_with_type_error():
    """Test cleaning tags when tags field causes TypeError."""
    row = FakeRow({'key': 'test', 'tags': {'not': 'list'}})
    result = clean_tags(row)
    assert result['tags'] == []


def test_clean_tags_preserves_other_fields():
    """Test that clean_tags preserves all other fields."""
    row = FakeRow({
        'key': 'test_key',
        'value': 'test_value',
        'expire_at': '2024-01-01',
        'tags': '["a", "b"]'
    })
    result = clean_tags(row)
    assert result['key'] == 'test_key'
    assert result['value'] == 'test_value'
    assert result['expire_at'] == '2024-01-01'
    assert result['tags'] == ['a', 'b']


def test_clean_tags_with_non_convertible_row():
    """Test that clean_tags handles rows that can't be converted to dict."""
    import pytest
    class BadRow:
        def __iter__(self):
            raise TypeError("Cannot iterate")

    row = BadRow()
    # This triggers the outer except block (lines 18-20), which tries to return
    # cleaned_row, but it was never assigned. This is a bug in the source code.
    with pytest.raises(UnboundLocalError):
        clean_tags(row)
