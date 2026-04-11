import hashlib
import json
import logging
import os
import time

logger = logging.getLogger(__name__)


class AnalysisCache:
    """File-based cache with TTL for stock analysis data."""

    def __init__(self, cache_dir: str = ".cache"):
        self._cache_dir = cache_dir

    def _ensure_dir(self):
        os.makedirs(self._cache_dir, exist_ok=True)

    def _path(self, key: str) -> str:
        safe = hashlib.md5(key.encode()).hexdigest()
        return os.path.join(self._cache_dir, f"{safe}.json")

    def make_key(self, tool_name: str, *args: str) -> str:
        return f"{tool_name}:{':'.join(args)}"

    def get(self, key: str) -> dict | None:
        path = self._path(key)
        if not os.path.exists(path):
            return None
        try:
            with open(path, "r") as f:
                entry = json.load(f)
            if time.time() > entry["expires_at"]:
                os.remove(path)
                return None
            return entry["value"]
        except (json.JSONDecodeError, KeyError, OSError):
            return None

    def set(self, key: str, value: dict, ttl_seconds: int):
        self._ensure_dir()
        entry = {"value": value, "expires_at": time.time() + ttl_seconds}
        path = self._path(key)
        with open(path, "w") as f:
            json.dump(entry, f)

    def invalidate(self, key: str):
        path = self._path(key)
        if os.path.exists(path):
            os.remove(path)
