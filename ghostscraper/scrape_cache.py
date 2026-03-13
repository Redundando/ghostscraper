"""ScrapeCache — lightweight cache backend for GhostScraper.

Replaces cacherator with a simple composition-based cache that supports
local JSON files or DynamoDB (never both simultaneously).
"""

import base64
import json
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Optional


class ScrapeCache:
    """Persistent cache with local-JSON or DynamoDB backend.

    Three modes:
      1. **No cache** — ``cache=False``: all methods are no-ops.
      2. **DynamoDB** — ``dynamodb_table`` is set: uses dynamorator only.
      3. **Local**  — default: JSON files in ``directory/``.
    """

    def __init__(
        self,
        key: str,
        directory: str = "data/ghostscraper",
        ttl: int = 999,
        dynamodb_table: Optional[str] = None,
        cache: bool = True,
        logging: bool = True,
    ):
        self._key = key
        self._directory = directory
        self._ttl = ttl
        self._cache = cache
        self._logging = logging
        self._dynamodb_table = dynamodb_table

        # Lazily initialised DynamoDB store
        self._db_store = None

    # ------------------------------------------------------------------
    # Backend helpers
    # ------------------------------------------------------------------

    @property
    def _is_disabled(self) -> bool:
        return not self._cache

    @property
    def _use_dynamodb(self) -> bool:
        return self._cache and self._dynamodb_table is not None

    @property
    def _use_local(self) -> bool:
        return self._cache and self._dynamodb_table is None

    def _get_db_store(self):
        if self._db_store is None:
            from dynamorator import DynamoDBStore
            self._db_store = DynamoDBStore(
                table_name=self._dynamodb_table,
                compress=True,
                silent=not self._logging,
            )
        return self._db_store

    def _local_path(self) -> Path:
        return Path(self._directory) / f"{self._key}.json"

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def save(self, data: dict) -> None:
        """Write *data* to local JSON **or** DynamoDB (not both)."""
        if self._is_disabled:
            return

        if self._use_dynamodb:
            self._get_db_store().put(self._key, data, ttl_days=self._ttl)
            return

        path = self._local_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "_saved_at": datetime.now().isoformat(),
            "_ttl_days": self._ttl,
            "data": data,
        }
        path.write_text(json.dumps(payload, indent=4, default=str), encoding="utf-8")

    def load(self) -> Optional[dict]:
        """Read back cached data. Returns ``None`` if expired / missing."""
        if self._is_disabled:
            return None

        if self._use_dynamodb:
            return self._get_db_store().get(self._key)

        path = self._local_path()
        if not path.exists():
            return None

        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return None

        saved_at = raw.get("_saved_at")
        ttl_days = raw.get("_ttl_days", self._ttl)
        if saved_at:
            try:
                saved_dt = datetime.fromisoformat(saved_at)
                if datetime.now() - saved_dt > timedelta(days=ttl_days):
                    return None
            except (ValueError, TypeError):
                pass

        return raw.get("data")

    def exists(self) -> bool:
        """Check if a cached entry exists **without** loading the full payload."""
        if self._is_disabled:
            return False

        if self._use_dynamodb:
            found = self._get_db_store().batch_get([self._key])
            return self._key in found

        path = self._local_path()
        if not path.exists():
            return False

        # Lightweight TTL check — read only the envelope, not the data
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return False

        saved_at = raw.get("_saved_at")
        ttl_days = raw.get("_ttl_days", self._ttl)
        if saved_at:
            try:
                saved_dt = datetime.fromisoformat(saved_at)
                if datetime.now() - saved_dt > timedelta(days=ttl_days):
                    return False
            except (ValueError, TypeError):
                pass

        return True

    def delete(self) -> None:
        """Remove this key from disk or DynamoDB."""
        if self._is_disabled:
            return

        if self._use_dynamodb:
            self._get_db_store().delete(self._key)
            return

        path = self._local_path()
        if path.exists():
            path.unlink()

    def list_keys(self, limit: int = 100, last_key: Optional[str] = None) -> dict:
        """List cached keys. Returns ``{"keys": [...], "last_key": ... }``."""
        if self._is_disabled:
            return {"keys": [], "last_key": None}

        if self._use_dynamodb:
            return self._get_db_store().list_keys(limit=limit, last_key=last_key)

        directory = Path(self._directory)
        if not directory.exists():
            return {"keys": [], "last_key": None}

        keys = sorted(
            p.stem for p in directory.glob("*.json")
        )
        return {"keys": keys[:limit], "last_key": None}

    # ------------------------------------------------------------------
    # Bytes helpers (for fetch_bytes)
    # ------------------------------------------------------------------

    def save_bytes(self, data: bytes, status_code: int, headers: dict) -> None:
        """Save binary *data* (base64-encoded) alongside status & headers."""
        self.save({
            "_bytes": base64.b64encode(data).decode(),
            "_status_code": status_code,
            "_headers": headers,
        })

    def load_bytes(self) -> Optional[tuple]:
        """Load binary data. Returns ``(bytes, status_code, headers)`` or ``None``."""
        cached = self.load()
        if cached is None:
            return None

        raw_bytes = cached.get("_bytes")
        if raw_bytes is None:
            return None

        return (
            base64.b64decode(raw_bytes),
            cached.get("_status_code"),
            cached.get("_headers", {}),
        )
