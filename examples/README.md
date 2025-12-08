# Cachetronomy Examples

This directory contains practical examples demonstrating various features of Cachetronomy.

## Running the Examples

```bash
# Run any example
python examples/01_basic_usage.py
```

## Examples Overview

### 01_basic_usage.py
**Demonstrates**: Fundamental cache operations

- Setting and getting values
- Using TTL (time-to-live)
- Bulk operations (`get_many`, `set_many`, `delete_many`)
- Health checks and statistics
- Proper cleanup

**Perfect for**: First-time users, understanding basic API

---

### 02_decorator_patterns.py
**Demonstrates**: Function caching with decorators

- Using `@cache` decorator for automatic caching
- Caching expensive computations
- Tag-based invalidation
- Async function caching
- `get_or_compute` for stampede protection

**Perfect for**: Optimizing function performance, preventing duplicate work

---

### 03_profiles_configuration.py
**Demonstrates**: Configuration management with profiles

- Creating custom profiles for different environments
- Switching between profiles
- Profile-based invalidation
- Environment-specific TTL and eviction settings
- Monitoring profile usage

**Perfect for**: Managing dev/staging/prod configurations

---

## Quick Start

```python
from cachetronomy import Cachetronaut

# Initialize
cache = Cachetronaut()

# Basic operations
cache.set('key', 'value', time_to_live=300)
value = cache.get('key')

# Bulk operations
cache.set_many({'key1': 'val1', 'key2': 'val2'})
results = cache.get_many(['key1', 'key2'])

# Decorator
@cache(time_to_live=60)
def expensive_function(x):
    return x * 2

# Monitoring
health = cache.health_check()
stats = cache.stats()

# Cleanup
cache.shutdown()
```

## Common Patterns

### Pattern 1: API Response Caching
```python
@cache(time_to_live=300, tags=['api'])
def fetch_api_data(endpoint):
    response = requests.get(endpoint)
    return response.json()

# Use the cached function
data = fetch_api_data('/users/1')

# Invalidate all API caches
cache.clear_by_tags(['api'], exact_match=False)
```

### Pattern 2: Database Query Caching
```python
@cache(time_to_live=600, tags=['db', 'users'])
def get_user_by_id(user_id):
    result = db.query("SELECT * FROM users WHERE id = ?", user_id)
    return result

# Cached query
user = get_user_by_id(123)

# Invalidate when user is updated
cache.delete(f'user:{123}')
```

### Pattern 3: Expensive Computation with Stampede Protection
```python
def generate_report():
    # Expensive operation
    return calculate_monthly_statistics()

# Multiple concurrent requests will only compute once
report = cache.get_or_compute(
    'monthly_report',
    generate_report,
    time_to_live=3600
)
```

### Pattern 4: Session Management
```python
# Store session
cache.set(f'session:{session_id}', session_data, time_to_live=1800)

# Retrieve session
session = cache.get(f'session:{session_id}')

# Delete session on logout
cache.delete(f'session:{session_id}')
```

## Best Practices

1. **Always set appropriate TTL**
   ```python
   cache.set('key', value, time_to_live=300)  # 5 minutes
   ```

2. **Use tags for bulk invalidation**
   ```python
   cache.set('key', value, tags=['users', 'api'])
   cache.clear_by_tags(['users'], exact_match=False)  # Invalidate all user-related cache
   ```

3. **Monitor cache health**
   ```python
   health = cache.health_check()
   if health['status'] != 'healthy':
       # Handle degraded state
       pass
   ```

4. **Use profiles for different environments**
   ```python
   if ENV == 'production':
       cache.set_profile('production')  # Longer TTL, more memory
   else:
       cache.set_profile('development')  # Shorter TTL, less memory
   ```

5. **Always cleanup on exit**
   ```python
   try:
       # Your code
       pass
   finally:
       cache.shutdown()
   ```

## Performance Tips

- Use `get_many`/`set_many` for batch operations
- Set appropriate TTL values based on data volatility
- Use tags for efficient invalidation
- Monitor `stats()` to track hit rates
- Use `get_or_compute` to prevent cache stampedes
- Configure profiles per environment (dev vs prod)

## Troubleshooting

### Cache misses even though data was set
- Check if TTL has expired
- Verify key spelling
- Check if data was evicted (memory pressure)

### High memory usage
- Reduce `max_items_in_memory` in profile
- Decrease TTL values
- Enable memory-based eviction

### Slow operations
- Check database size (`stats()`)
- Consider using tags for faster invalidation
- Use bulk operations for multiple keys

## Learn More

- [Full Documentation](https://github.com/cachetronaut/cachetronomy)
- [API Reference](https://github.com/cachetronaut/cachetronomy/wiki/API-Reference)
- [Best Practices Guide](https://github.com/cachetronaut/cachetronomy/wiki/Best-Practices)
