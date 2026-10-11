"""Small TTL cache for list endpoints. /v1/validate never uses it (validation is always live)."""

from __future__ import annotations

import threading
import time
from collections.abc import Callable
from typing import Any


class TtlCache:
    def __init__(self, ttl_seconds: int) -> None:
        self.ttl = ttl_seconds
        self._data: dict[str, tuple[float, Any]] = {}
        self._lock = threading.Lock()
        self.hits = 0
        self.misses = 0

    def get_or_load(self, key: str, loader: Callable[[], Any]) -> Any:
        now = time.monotonic()
        with self._lock:
            entry = self._data.get(key)
            if entry and entry[0] > now:
                self.hits += 1
                return entry[1]
        value = loader()
        with self._lock:
            self.misses += 1
            self._data[key] = (now + self.ttl, value)
        return value
