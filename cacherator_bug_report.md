# Bug Report: json_cache_save() doesn't sync to DynamoDB

## Environment
- **cacherator version**: 1.2.1
- **Python version**: 3.14
- **OS**: Windows

## Description

According to the documentation, when DynamoDB is enabled, writes should be "Saved to both L1 and L2 simultaneously". However, `json_cache_save()` only writes to local JSON (L1) and does NOT sync to DynamoDB (L2).

## Expected Behavior

When calling `json_cache_save()` with DynamoDB enabled, the cache should be written to:
1. Local JSON file (L1 cache)
2. DynamoDB table (L2 cache)

## Actual Behavior

`json_cache_save()` only writes to local JSON. DynamoDB is NOT updated unless:
1. `clear_cache=True` is used during `__init__` (writes empty state to DynamoDB)
2. The private method `_write_to_dynamodb()` is called manually

## Reproduction Steps

```python
from cacherator import JSONCache

class TestCache(JSONCache):
    def __init__(self):
        super().__init__(
            data_id="test",
            dynamodb_table="my-cache-table"
        )
        self.data = None

# Create instance
cache = TestCache()

# Set data and save
cache.data = "Hello World"
cache.json_cache_save()

# Expected: DynamoDB put operation should happen
# Actual: Only local JSON is written, no DynamoDB put
```

## Observed Logs

With `logging=True`, we see:

**During __init__ with clear_cache=True:**
```
Running [DynamoDBStore(table_name=my-cache-table)] put
  key: test
Finished put  Time elapsed: 125.81 ms
```

**After json_cache_save():**
```
(no DynamoDB operation logged - only local JSON is written)
```

## Workaround

Manually call the private method `_write_to_dynamodb()`:

```python
cache.data = "Hello World"
cache.json_cache_save()

# Workaround: Force DynamoDB sync
if cache._dynamodb_enabled:
    cache._write_to_dynamodb()
```

This produces the expected DynamoDB put operation:
```
Running [DynamoDBStore(table_name=my-cache-table)] put
  key: test
Finished put  Time elapsed: 122.05 ms
```

## Expected Fix

Either:
1. Make `json_cache_save()` automatically call `_write_to_dynamodb()` when DynamoDB is enabled
2. Provide a public method like `json_cache_save(sync_dynamodb=True)` to control DynamoDB syncing
3. Update documentation to clarify that DynamoDB writes only happen during `__init__` and `__del__`

## Impact

This breaks the documented behavior of two-tier caching. Users expecting automatic DynamoDB sync will have stale data in DynamoDB, defeating the purpose of cross-machine cache sharing.

## Additional Context

The issue was discovered while implementing DynamoDB caching in the ghostscraper package. We need to explicitly call `_write_to_dynamodb()` after every cache update to ensure DynamoDB stays in sync with local cache.
