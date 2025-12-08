"""
Decorator Patterns

This example shows how to use the @cache decorator to automatically
cache function results, reducing expensive computations.
"""

import time
from cachetronomy import Cachetronaut

cache = Cachetronaut(db_path='decorator_cache.db')

# === Basic Decorator Usage ===
print("=== Basic Decorator ===")

@cache(time_to_live=60)
def expensive_computation(n: int) -> int:
    """Simulate an expensive operation."""
    print(f"  Computing fibonacci({n})...")
    time.sleep(0.1)  # Simulate work
    if n <= 1:
        return n
    return expensive_computation(n-1) + expensive_computation(n-2)

# First call - computes
start = time.time()
result1 = expensive_computation(10)
time1 = time.time() - start
print(f"✓ First call: {result1} (took {time1:.3f}s)")

# Second call - from cache
start = time.time()
result2 = expensive_computation(10)
time2 = time.time() - start
print(f"✓ Second call: {result2} (took {time2:.3f}s - cached!)")

# === Tags for Invalidation ===
print("\n=== Using Tags ===")

@cache(time_to_live=300, tags=['api', 'users'])
def fetch_user_data(user_id: int) -> dict:
    """Fetch user data (simulated)."""
    print(f"  Fetching user {user_id} from API...")
    time.sleep(0.05)
    return {
        'id': user_id,
        'name': f'User{user_id}',
        'email': f'user{user_id}@example.com'
    }

user1 = fetch_user_data(1)
print(f"✓ Fetched: {user1['name']}")

user2 = fetch_user_data(2)
print(f"✓ Fetched: {user2['name']}")

# Invalidate all entries with 'users' tag
cache.clear_by_tags(['users'], exact_match=False)
print("✓ Invalidated all user cache entries")

# Next call will recompute
user1_fresh = fetch_user_data(1)
print(f"✓ Re-fetched: {user1_fresh['name']}")

# === Async Functions ===
print("\n=== Async Decorator ===")

@cache(time_to_live=60)
async def async_api_call(endpoint: str) -> dict:
    """Simulate async API call."""
    print(f"  Calling API: {endpoint}")
    import asyncio
    await asyncio.sleep(0.1)
    return {'endpoint': endpoint, 'data': 'response'}

import asyncio

# Use async function
result = asyncio.run(async_api_call('/users'))
print(f"✓ API call: {result}")

# Cached version
result2 = asyncio.run(async_api_call('/users'))
print(f"✓ Cached API call: {result2}")

# === get_or_compute Pattern ===
print("\n=== get_or_compute (Stampede Protection) ===")

def compute_expensive_report():
    """Simulate expensive report generation."""
    print("  Generating expensive report...")
    time.sleep(0.2)
    return {'report': 'data', 'rows': 1000}

# Multiple concurrent calls will only compute once
report = cache.get_or_compute(
    'monthly_report',
    compute_expensive_report,
    time_to_live=3600
)
print(f"✓ Report generated: {report['rows']} rows")

# Subsequent calls use cache
report2 = cache.get_or_compute(
    'monthly_report',
    lambda: {'should': 'not be called'},
    time_to_live=3600
)
print(f"✓ Report from cache: {report2['rows']} rows")

# Cleanup
cache.clear_all()
cache.shutdown()
print("\n✓ Example complete")
