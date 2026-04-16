# Stock Analysis AI Agent - Multi-Exchange Stock Analysis Platform
# Copyright (C) 2026 B.Vignesh Kumar (Bravetux) <ic19939@gmail.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <https://www.gnu.org/licenses/>.
#
# Author: B.Vignesh Kumar aka Bravetux
# Email:  ic19939@gmail.com
# Developed: 10th April 2026

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
