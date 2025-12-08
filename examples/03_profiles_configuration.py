"""
Profiles and Configuration

This example demonstrates how to use profiles to manage different
caching strategies for different environments or use cases.
"""

from cachetronomy import Cachetronaut, Profile

cache = Cachetronaut(db_path='profiles_cache.db')

# === List Available Profiles ===
print("=== Available Profiles ===")

profiles = cache.list_profiles()
for prof in profiles:
    print(f"✓ {prof.name}:")
    print(f"  - TTL: {prof.time_to_live}s")
    print(f"  - Memory eviction: {prof.memory_based_eviction}")
    print(f"  - Max items in memory: {prof.max_items_in_memory}")

# === Create Custom Profile ===
print("\n=== Creating Custom Profile ===")

# Profile for dev environment - shorter TTLs, more aggressive eviction
dev_profile = Profile(
    name='development',
    time_to_live=60,  # 1 minute
    ttl_cleanup_interval=10,  # Check every 10s
    memory_based_eviction=True,
    free_memory_target=1000.0,  # 1GB
    memory_cleanup_interval=5,
    max_items_in_memory=50,
    tags=['dev', 'local']
)

cache.update_active_profile(dev_profile)
print(f"✓ Created and activated profile: {dev_profile.name}")

# Use cache with dev profile
cache.set('dev:key1', 'value1')  # Uses 60s TTL from profile
print("✓ Stored key with dev profile settings")

# === Create Production Profile ===
print("\n=== Creating Production Profile ===")

prod_profile = Profile(
    name='production',
    time_to_live=3600,  # 1 hour
    ttl_cleanup_interval=300,  # Check every 5 minutes
    memory_based_eviction=True,
    free_memory_target=500.0,  # 500MB
    memory_cleanup_interval=30,
    max_items_in_memory=1000,
    tags=['prod', 'stable']
)

cache.update_active_profile(prod_profile)
print(f"✓ Created and activated profile: {prod_profile.name}")

# Use cache with prod profile
cache.set('prod:key1', 'value1')  # Uses 3600s TTL from profile
print("✓ Stored key with production profile settings")

# === Switch Between Profiles ===
print("\n=== Switching Profiles ===")

# Switch back to default
cache.set_profile('default')
print(f"✓ Switched to: {cache.profile.name}")

# Switch to production
cache.set_profile('production')
print(f"✓ Switched to: {cache.profile.name}")

# === Profile-Based Invalidation ===
print("\n=== Profile-Based Operations ===")

# Store data with different profiles
cache.set_profile('development')
cache.set('temp:data1', 'dev data 1')
cache.set('temp:data2', 'dev data 2')

cache.set_profile('production')
cache.set('temp:data3', 'prod data 3')

print("✓ Stored data across 2 profiles")

# Clear only dev profile data
cache.clear_by_profile('development')
print("✓ Cleared all development profile data")

# Check what remains
remaining = cache.get('temp:data3')
print(f"✓ Production data still exists: {remaining}")

# === Monitor Profile Usage ===
print("\n=== Profile Statistics ===")

stats = cache.stats()
print(f"✓ Current profile: {stats['profile']}")
print(f"  - Total keys: {stats['total_keys']}")
print(f"  - Memory keys: {stats['memory_keys']}")

# Cleanup
cache.clear_all()
cache.shutdown()
print("\n✓ Example complete")
