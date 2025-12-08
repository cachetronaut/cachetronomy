"""
Tests for Profile model and related functionality.
"""
import pytest
import tempfile
from pathlib import Path
from cachetronomy.core.types.profiles import Profile


def test_profile_creation_with_defaults():
    """Test creating a Profile with default values."""
    profile = Profile(name="test")
    assert profile.name == "test"
    assert profile.time_to_live == 3600
    assert profile.ttl_cleanup_interval == 60
    assert profile.memory_based_eviction == True
    assert profile.free_memory_target == 500.0
    assert profile.memory_cleanup_interval == 5
    assert profile.max_items_in_memory == 100
    assert profile.tags == []


def test_profile_creation_with_custom_values():
    """Test creating a Profile with custom values."""
    profile = Profile(
        name="custom",
        time_to_live=7200,
        ttl_cleanup_interval=120,
        memory_based_eviction=False,
        free_memory_target=1000.0,
        memory_cleanup_interval=10,
        max_items_in_memory=200,
        tags=["tag1", "tag2"]
    )
    assert profile.name == "custom"
    assert profile.time_to_live == 7200
    assert profile.ttl_cleanup_interval == 120
    assert profile.memory_based_eviction == False
    assert profile.free_memory_target == 1000.0
    assert profile.memory_cleanup_interval == 10
    assert profile.max_items_in_memory == 200
    assert profile.tags == ["tag1", "tag2"]


def test_profile_time_to_live_validation():
    """Test that time_to_live must be greater than 0."""
    with pytest.raises(ValueError):
        Profile(name="test", time_to_live=0)

    with pytest.raises(ValueError):
        Profile(name="test", time_to_live=-1)


def test_profile_ttl_cleanup_interval_validation():
    """Test that ttl_cleanup_interval must be >= 0."""
    profile = Profile(name="test", ttl_cleanup_interval=0)
    assert profile.ttl_cleanup_interval == 0

    with pytest.raises(ValueError):
        Profile(name="test", ttl_cleanup_interval=-1)


def test_profile_free_memory_target_validation():
    """Test that free_memory_target must be >= 0."""
    profile = Profile(name="test", free_memory_target=0.0)
    assert profile.free_memory_target == 0.0

    with pytest.raises(ValueError):
        Profile(name="test", free_memory_target=-1.0)


def test_profile_memory_cleanup_interval_validation():
    """Test that memory_cleanup_interval must be >= 0."""
    profile = Profile(name="test", memory_cleanup_interval=0)
    assert profile.memory_cleanup_interval == 0

    with pytest.raises(ValueError):
        Profile(name="test", memory_cleanup_interval=-1)


def test_profile_max_items_in_memory_validation():
    """Test that max_items_in_memory must be >= 0."""
    profile = Profile(name="test", max_items_in_memory=0)
    assert profile.max_items_in_memory == 0

    with pytest.raises(ValueError):
        Profile(name="test", max_items_in_memory=-1)


def test_profile_load_profiles_from_yaml():
    """Test loading profiles from a YAML file."""
    yaml_content = """
default:
  time_to_live: 3600
  ttl_cleanup_interval: 60
  memory_based_eviction: true
  free_memory_target: 500.0
  memory_cleanup_interval: 5
  max_items_in_memory: 100
  tags: []

production:
  time_to_live: 7200
  ttl_cleanup_interval: 120
  memory_based_eviction: false
  free_memory_target: 1000.0
  memory_cleanup_interval: 10
  max_items_in_memory: 200
  tags: ["prod", "cache"]
"""

    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        f.write(yaml_content)
        temp_path = Path(f.name)

    try:
        profiles = Profile.load_profiles(temp_path)

        assert "default" in profiles
        assert "production" in profiles

        default = profiles["default"]
        assert default.name == "default"
        assert default.time_to_live == 3600
        assert default.max_items_in_memory == 100

        production = profiles["production"]
        assert production.name == "production"
        assert production.time_to_live == 7200
        assert production.memory_based_eviction == False
        assert production.tags == ["prod", "cache"]
    finally:
        temp_path.unlink(missing_ok=True)


def test_profile_model_dump():
    """Test that Profile can be serialized to dict."""
    profile = Profile(name="test", tags=["tag1"])
    data = profile.model_dump()

    assert data['name'] == "test"
    assert data['tags'] == ["tag1"]
    assert 'time_to_live' in data
    assert 'memory_based_eviction' in data
