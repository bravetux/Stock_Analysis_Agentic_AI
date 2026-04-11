import os
import json
import time
import shutil
import pytest
from src.utils.cache import AnalysisCache


@pytest.fixture
def cache(tmp_path):
    return AnalysisCache(cache_dir=str(tmp_path / "test_cache"))


class TestAnalysisCache:
    def test_set_and_get(self, cache):
        cache.set("test_key", {"price": 100}, ttl_seconds=60)
        result = cache.get("test_key")
        assert result == {"price": 100}

    def test_get_missing_key(self, cache):
        result = cache.get("nonexistent")
        assert result is None

    def test_expired_entry(self, cache):
        cache.set("expire_key", {"data": 1}, ttl_seconds=1)
        time.sleep(1.1)
        result = cache.get("expire_key")
        assert result is None

    def test_invalidate(self, cache):
        cache.set("del_key", {"data": 1}, ttl_seconds=60)
        cache.invalidate("del_key")
        result = cache.get("del_key")
        assert result is None

    def test_invalidate_missing_key(self, cache):
        cache.invalidate("nonexistent")  # should not raise

    def test_make_key(self, cache):
        key = cache.make_key("calculate_200dma", "RELIANCE", "NSE")
        assert "calculate_200dma" in key
        assert "RELIANCE" in key
        assert "NSE" in key

    def test_creates_cache_directory(self, tmp_path):
        cache_dir = str(tmp_path / "new_cache_dir")
        cache = AnalysisCache(cache_dir=cache_dir)
        cache.set("k", {"v": 1}, ttl_seconds=60)
        assert os.path.isdir(cache_dir)
