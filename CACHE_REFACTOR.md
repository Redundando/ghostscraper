# Cache Refactor Battle Plan

## Why

Cacherator (v1.2.1) causes problems:
1. **Auto-restore on init** loads full HTML into memory — kills `scrape_stream`
2. **Weakref finalizer** auto-saves on GC — dangerous for lazy/empty instances
3. **Inheritance coupling** — GhostScraper *is* a JSONCache, tight coupling
4. **DynamoDB writes may be broken** — `json_cache_save()` only writes local JSON; DynamoDB requires `json_cache_save_db()` which GhostScraper never calls for HTML fetch
5. **No `exists()` check** — can't check cache without loading full payload
6. We use ~5% of Cacherator's features

## What We Build

A `ScrapeCache` class (~100 lines) used via **composition** (not inheritance).

### ScrapeCache API

```python
class ScrapeCache:
    def __init__(self, key: str, directory: str, ttl: int, dynamodb_table: str | None, logging: bool):
        ...

    def save(self, data: dict) -> None:
        """Write data to local JSON or DynamoDB (not both — DynamoDB replaces local when set)."""

    def load(self) -> dict | None:
        """Read back, check TTL, return None if expired/missing."""

    def exists(self) -> bool:
        """Check if cached without loading payload. Uses DynamoDB batch_get or local file check."""

    def delete(self) -> None:
        """Remove from disk or DynamoDB."""

    def list_keys(self, limit=100, last_key=None) -> dict:
        """Delegate to dynamorator. Local: list JSON files in directory."""

    def save_bytes(self, data: bytes, status_code: int, headers: dict) -> None:
        """Save binary data (base64-encoded) for fetch_bytes."""

    def load_bytes(self) -> tuple[bytes, int, dict] | None:
        """Load binary data for fetch_bytes."""
```

### Backend Logic — Three Modes

1. **No cache** — `cache=False` → never read or write cache. Every call fetches fresh.
2. **DynamoDB** — `dynamodb_table` is set → DynamoDB only via dynamorator (`compress=True`). No local files.
3. **Local** — default (`cache=True`, no `dynamodb_table`) → JSON files in `directory/`.

Never both simultaneously. `ScrapeCache` picks one backend at init and sticks with it.

When `cache=False`, all methods are no-ops:
- `save()` / `save_bytes()` → do nothing
- `load()` / `load_bytes()` → return `None`
- `exists()` → return `False`
- `delete()` → do nothing
- `clear_cache` is ignored when `cache=False`

### GhostScraper Constructor Changes

```python
GhostScraper(
    url="",
    cache=True,              # NEW — False disables all caching
    clear_cache=False,
    ttl=999,
    dynamodb_table=None,     # Set to enable DynamoDB-only caching
    ...                      # everything else unchanged
)
```

Backward compatible: existing code that passes nothing gets local cache, existing code that passes `dynamodb_table` gets DynamoDB, new code can pass `cache=False` to disable.

### Data Format (local JSON)

```json
{
    "_saved_at": "2026-01-15T10:30:00",
    "_ttl_days": 999,
    "data": {
        "_html": "...",
        "_response_code": 200,
        "_response_headers": {},
        "_redirect_chain": []
    }
}
```

### Data Format (DynamoDB)

Same `data` dict, stored via `dynamorator.put(key, payload, ttl_days)`.

## GhostScraper Changes

### Before (inheritance)
```python
class GhostScraper(JSONCache):
    def __init__(self, ...):
        JSONCache.__init__(self, data_id=slugify(url), ...)
        # _html magically restored by JSONCache
```

### After (composition)
```python
class GhostScraper:
    def __init__(self, ..., lazy=False):
        self._cache = ScrapeCache(key=slugify(url), ...)
        if not lazy:
            self._restore_from_cache()

    def _restore_from_cache(self):
        data = self._cache.load()
        if data:
            self._html = data.get("_html")
            self._response_code = data.get("_response_code")
            # etc.
```

### `lazy=True` (for scrape_stream)
- Creates the ScrapeCache but does NOT call `load()`
- First call to `get_response()` triggers `_restore_from_cache()`
- Parent process stays lightweight

### Deprecated Method Shims

| Old (cacherator) | New | Behavior |
|---|---|---|
| `json_cache_save()` | `save_cache()` | Save persisted fields |
| `json_cache_save_db()` | `save_cache()` | Same — no dual-backend |
| `json_cache_clear()` | `clear_cache_entry()` | Delete this URL's cache |
| `json_cache_stats()` | `cache_stats()` | Return basic stats |
| `json_cache_list_db_keys()` | `cache_list_keys()` | List keys |
| `set_logging()` | `set_logging()` | Keep as-is |

Old names call new names + emit `DeprecationWarning`.

### fetch_bytes Changes

Replace standalone `JSONCache(data_id=f"bytes-{slugify(url)}")` with `ScrapeCache(key=f"bytes-{slugify(url)}")` using `save_bytes()` / `load_bytes()`.

### @Cached() on _playwright_scraper

Replace with simple lazy init:
```python
@property
def _playwright_scraper(self):
    if self.__playwright_scraper is None:
        self.__playwright_scraper = PlaywrightScraper(...)
    return self.__playwright_scraper
```

## Phases

### Phase R1: ScrapeCache

**Files:** `ghostscraper/scrape_cache.py`

Build the ScrapeCache class:
- Local JSON backend (read/write/exists/delete/list)
- DynamoDB backend via dynamorator (read/write/exists/delete/list)
- TTL checking for local files
- Bytes support (base64 encode/decode)
- gzip compression via dynamorator's `compress=True`

**Test:** Create cache, save, load, check exists, check TTL expiry, delete, bytes round-trip.

**Done when:** All cache operations work for both backends.

### Phase R2: Swap GhostScraper to ScrapeCache

**Files:** `ghostscraper/ghost_scraper.py`

- Remove `JSONCache` inheritance
- Add `ScrapeCache` composition
- Add `lazy` parameter
- Replace `json_cache_save()` calls with `save_cache()`
- Replace `@Cached()` with lazy property
- Add deprecated method shims
- Update `fetch_bytes` to use ScrapeCache

**Test:** Run existing test suite. Verify single URL, batch, fetch_bytes, DynamoDB all still work.

**Done when:** All existing functionality works without cacherator.

### Phase R3: Fix scrape_stream Memory

**Files:** `ghostscraper/stream/scrape_stream.py`

- Use `lazy=True` when constructing scrapers in the parent
- Use `ScrapeCache.exists()` for cache checking (no payload load)

**Test:** Re-run the heavy Audible test. Memory should stay flat.

**Done when:** 70 URLs, parent memory stays under ~80-90 MB.

### Phase R4: Cleanup

**Files:** `pyproject.toml`, `requirements.txt`, `__init__.py`

- Remove `cacherator` from dependencies
- Update exports if needed
- Verify `dynamorator` stays as dependency

**Done when:** `pip install ghostscraper` no longer pulls cacherator.

## Progress Tracker

| Phase | Description | Status |
|-------|-------------|--------|
| R1 | ScrapeCache | ✅ Done |
| R2 | Swap GhostScraper | ✅ Done |
| R3 | Fix scrape_stream memory | ✅ Done |
| R4 | Cleanup | ✅ Done |
