"""
Basic Usage Examples

This example demonstrates the fundamental operations of Cachetronomy:
- Setting and getting values
- Using TTL (time-to-live)
- Deleting entries
- Checking cache status
"""

from cachetronomy import Cachetronaut

# Initialize cache (stores in current directory by default)
cache = Cachetronaut(db_path='example_cache.db')

# === Basic Get/Set ===
print("=== Basic Operations ===")

# Set a value
cache.set('user:1', {'name': 'Alice', 'email': 'alice@example.com'})
print("✓ Stored user data")

# Get a value
user = cache.get('user:1')
print(f"✓ Retrieved: {user}")

# Set with TTL (time to live in seconds)
cache.set('session:abc123', {'user_id': 1}, time_to_live=300)  # 5 minutes
print("✓ Stored session with 5-minute TTL")

# === Bulk Operations ===
print("\n=== Bulk Operations ===")

# Set multiple values at once
cache.set_many({
    'product:1': {'name': 'Laptop', 'price': 999},
    'product:2': {'name': 'Mouse', 'price': 29},
    'product:3': {'name': 'Keyboard', 'price': 79},
})
print("✓ Stored 3 products")

# Get multiple values at once
products = cache.get_many(['product:1', 'product:2', 'product:999'])
print(f"✓ Retrieved {len(products)} products (product:999 doesn't exist)")

# Delete multiple values
deleted = cache.delete_many(['product:2', 'product:3'])
print(f"✓ Deleted {deleted} products")

# === Health Check & Statistics ===
print("\n=== Monitoring ===")

health = cache.health_check()
print(f"✓ Health: {health['status']}")
print(f"  - DB accessible: {health['db_accessible']}")
print(f"  - Store keys: {health['store_keys_count']}")
print(f"  - Memory keys: {health['memory_keys_count']}")

stats = cache.stats()
print(f"\n✓ Stats:")
print(f"  - Total keys: {stats['total_keys']}")
print(f"  - Profile: {stats['profile']}")
print(f"  - Evictions: {stats['evictions_count']}")

# === Cleanup ===
cache.clear_all()
cache.shutdown()
print("\n✓ Cleaned up and shut down")
