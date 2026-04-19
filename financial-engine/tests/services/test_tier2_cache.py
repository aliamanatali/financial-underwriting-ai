"""
Tests for Tier 2 cache hygiene changes.

2.1 Redis TTL reduced to 7 days; invalidation on user correction
2.2 Confidence-gated cache writes; original confidence replayed
2.3 Cache observability endpoints (GET /cache/mappings, POST /cache/clear)
2.4 Cache key migration (old→new format fallback with forward-write)
"""

import pytest
import json
from unittest.mock import MagicMock, AsyncMock, patch, PropertyMock
from app.services.normalization_service import NormalizationService
from app.models.schemas import ExpenseCategory


@pytest.fixture
def norm_service():
    return NormalizationService(llm_service=MagicMock())


# ---------------------------------------------------------------------------
# Helper: Mock Redis client that stores data in a plain dict
# ---------------------------------------------------------------------------

class FakeRedisClient:
    """In-memory Redis-like object for testing cache behavior."""

    def __init__(self):
        self.store = {}
        self.ttls = {}

    async def mget(self, keys):
        return [self.store.get(k) for k in keys]

    async def get(self, key):
        return self.store.get(key)

    async def set(self, key, value, ex=None):
        self.store[key] = value
        if ex:
            self.ttls[key] = ex

    async def delete(self, *keys):
        for k in keys:
            self.store.pop(k, None)
            self.ttls.pop(k, None)

    def pipeline(self):
        return FakePipeline(self)

    async def scan_iter(self, match=None, count=100):
        import fnmatch
        for key in list(self.store.keys()):
            if match is None or fnmatch.fnmatch(key, match):
                yield key

    async def ttl(self, key):
        return self.ttls.get(key, -1)


class FakePipeline:
    def __init__(self, redis):
        self._redis = redis
        self._ops = []

    def set(self, key, value, ex=None):
        self._ops.append(("set", key, value, ex))
        return self

    async def execute(self):
        for op in self._ops:
            if op[0] == "set":
                _, key, value, ex = op
                self._redis.store[key] = value
                if ex:
                    self._redis.ttls[key] = ex
        self._ops.clear()


# ===========================================================================
# 2.1  Redis TTL reduced to 7 days
# ===========================================================================

class TestCacheTTL:

    def test_ttl_constant_is_7_days(self):
        assert NormalizationService.CACHE_TTL_SECONDS == 86400 * 7

    @pytest.mark.asyncio
    async def test_save_mappings_uses_7_day_ttl(self, norm_service):
        """Cached entries get a 7-day TTL, not 30 days."""
        fake_redis = FakeRedisClient()
        mapping = [{
            "original_text": "Electric Bill",
            "mapped_category": "Utilities",
            "confidence": 0.92,
            "reasoning": "Utility provider",
        }]

        with patch("app.db.redis.redis_client") as mock_rc, \
             patch("app.config.settings") as mock_settings:
            mock_rc.client = fake_redis
            mock_settings.use_mongodb = False

            await norm_service._save_mappings(mapping)

        key = NormalizationService._cache_key("Electric Bill", "unknown")
        assert key in fake_redis.store
        assert fake_redis.ttls[key] == 86400 * 7


# ===========================================================================
# 2.2  Confidence-gated cache writes
# ===========================================================================

class TestConfidenceGating:

    @pytest.mark.asyncio
    async def test_low_confidence_not_cached_in_redis(self, norm_service):
        """Mappings with confidence < 0.85 should NOT be written to Redis."""
        fake_redis = FakeRedisClient()
        mapping = [{
            "original_text": "Ambiguous Item",
            "mapped_category": "Other Operating Expenses",
            "confidence": 0.70,
            "reasoning": "Uncertain classification",
        }]

        with patch("app.db.redis.redis_client") as mock_rc, \
             patch("app.config.settings") as mock_settings:
            mock_rc.client = fake_redis
            mock_settings.use_mongodb = False

            await norm_service._save_mappings(mapping)

        # Should NOT be in Redis
        assert len(fake_redis.store) == 0

    @pytest.mark.asyncio
    async def test_high_confidence_cached_in_redis(self, norm_service):
        """Mappings with confidence >= 0.85 should be cached."""
        fake_redis = FakeRedisClient()
        mapping = [{
            "original_text": "Property Tax",
            "mapped_category": "Real Estate Taxes",
            "confidence": 0.95,
            "reasoning": "Tax keyword match",
        }]

        with patch("app.db.redis.redis_client") as mock_rc, \
             patch("app.config.settings") as mock_settings:
            mock_rc.client = fake_redis
            mock_settings.use_mongodb = False

            await norm_service._save_mappings(mapping)

        key = NormalizationService._cache_key("Property Tax", "unknown")
        assert key in fake_redis.store
        stored = json.loads(fake_redis.store[key])
        assert stored["confidence"] == 0.95

    @pytest.mark.asyncio
    async def test_cache_hit_replays_original_confidence(self, norm_service):
        """Cache hit returns the original LLM confidence, not a hardcoded value."""
        fake_redis = FakeRedisClient()
        # Pre-populate cache with a 0.88 confidence entry
        cached_entry = {
            "original_text": "Plumbing Repair",
            "mapped_category": "Repairs & Maintenance",
            "confidence": 0.88,
            "reasoning": "Maintenance item",
        }
        key = NormalizationService._cache_key("Plumbing Repair", "unknown")
        fake_redis.store[key] = json.dumps(cached_entry)

        with patch("app.db.redis.redis_client") as mock_rc, \
             patch("app.config.settings") as mock_settings:
            mock_rc.client = fake_redis
            mock_settings.use_mongodb = False

            result = await norm_service._get_cached_mappings(["Plumbing Repair"])

        assert "Plumbing Repair" in result
        assert result["Plumbing Repair"]["confidence"] == 0.88


# ===========================================================================
# 2.3  Cache invalidation on user correction
# ===========================================================================

class TestCacheInvalidation:

    @pytest.mark.asyncio
    async def test_invalidation_removes_from_redis(self):
        """invalidate_cache_entry removes both new and legacy key formats."""
        fake_redis = FakeRedisClient()
        # Populate both key formats
        fake_redis.store["mapping:Water & Sewer:unknown"] = json.dumps({"mapped_category": "Utilities"})
        fake_redis.store["mapping:Water & Sewer"] = json.dumps({"mapped_category": "Utilities"})

        with patch("app.db.redis.redis_client") as mock_rc, \
             patch("app.config.settings") as mock_settings:
            mock_rc.client = fake_redis
            mock_settings.use_mongodb = False

            await NormalizationService.invalidate_cache_entry("Water & Sewer")

        assert "mapping:Water & Sewer:unknown" not in fake_redis.store
        assert "mapping:Water & Sewer" not in fake_redis.store


# ===========================================================================
# 2.4  Cache key migration — old format → new format fallback
# ===========================================================================

class TestCacheKeyMigration:

    def test_new_key_format(self):
        key = NormalizationService._cache_key("Parking", "income")
        assert key == "mapping:Parking:income"

    def test_legacy_key_format(self):
        key = NormalizationService._legacy_cache_key("Parking")
        assert key == "mapping:Parking"

    @pytest.mark.asyncio
    async def test_legacy_key_fallback_and_forward_write(self, norm_service):
        """If new key misses but legacy key hits, return value AND forward-write new key."""
        fake_redis = FakeRedisClient()
        # Only legacy key exists
        cached = {"original_text": "Parking", "mapped_category": "Other Income", "confidence": 0.90}
        fake_redis.store["mapping:Parking"] = json.dumps(cached)

        with patch("app.db.redis.redis_client") as mock_rc, \
             patch("app.config.settings") as mock_settings:
            mock_rc.client = fake_redis
            mock_settings.use_mongodb = False

            result = await norm_service._get_cached_mappings(["Parking"])

        # Should have found the value via legacy fallback
        assert "Parking" in result
        assert result["Parking"]["mapped_category"] == "Other Income"

        # Forward-written under new key format
        new_key = NormalizationService._cache_key("Parking", "unknown")
        assert new_key in fake_redis.store
        assert fake_redis.ttls[new_key] == NormalizationService.CACHE_TTL_SECONDS

    @pytest.mark.asyncio
    async def test_new_key_takes_priority_over_legacy(self, norm_service):
        """If new key exists, legacy key is not consulted."""
        fake_redis = FakeRedisClient()
        # New key has updated value
        new_cached = {"original_text": "Parking", "mapped_category": "Other Income", "confidence": 0.95}
        fake_redis.store["mapping:Parking:unknown"] = json.dumps(new_cached)
        # Legacy key has stale value
        legacy_cached = {"original_text": "Parking", "mapped_category": "Other Operating Expenses", "confidence": 0.80}
        fake_redis.store["mapping:Parking"] = json.dumps(legacy_cached)

        with patch("app.db.redis.redis_client") as mock_rc, \
             patch("app.config.settings") as mock_settings:
            mock_rc.client = fake_redis
            mock_settings.use_mongodb = False

            result = await norm_service._get_cached_mappings(["Parking"])

        assert result["Parking"]["mapped_category"] == "Other Income"
        assert result["Parking"]["confidence"] == 0.95


# ===========================================================================
# 2.3  Cache observability endpoints (integration-style via TestClient)
# ===========================================================================

class TestCacheEndpoints:
    """Test the cache debug/clear endpoints via the FastAPI test client."""

    @pytest.mark.asyncio
    async def test_cache_mappings_endpoint(self):
        """GET /api/v1/cache/mappings returns matching entries."""
        from fastapi.testclient import TestClient
        from app.main import app
        from app.db import redis as redis_module

        fake_redis = FakeRedisClient()
        cached = {"original_text": "Repair - HVAC", "mapped_category": "Repairs & Maintenance", "confidence": 0.90}
        fake_redis.store["mapping:Repair - HVAC:unknown"] = json.dumps(cached)

        original_client = redis_module.redis_client.client
        redis_module.redis_client.client = fake_redis
        try:
            client = TestClient(app)
            response = client.get("/api/v1/cache/mappings", params={"prefix": "Repair"})
        finally:
            redis_module.redis_client.client = original_client

        assert response.status_code == 200
        data = response.json()
        # At minimum, the Redis entry should appear
        redis_entries = [e for e in data["entries"] if e.get("source") == "redis"]
        assert len(redis_entries) >= 1
        assert any(e.get("original_text") == "Repair - HVAC" for e in redis_entries)

    @pytest.mark.asyncio
    async def test_cache_clear_endpoint(self):
        """POST /api/v1/cache/clear removes specified entries."""
        from fastapi.testclient import TestClient
        from app.main import app
        from app.db import redis as redis_module

        fake_redis = FakeRedisClient()
        cached = {"original_text": "Bad Entry", "mapped_category": "Uncategorized", "confidence": 0.50}
        fake_redis.store["mapping:Bad Entry:unknown"] = json.dumps(cached)
        fake_redis.store["mapping:Bad Entry"] = json.dumps(cached)

        original_client = redis_module.redis_client.client
        redis_module.redis_client.client = fake_redis
        try:
            client = TestClient(app)
            response = client.post(
                "/api/v1/cache/clear",
                json={"descriptions": ["Bad Entry"]},
            )
        finally:
            redis_module.redis_client.client = original_client

        assert response.status_code == 200
        data = response.json()
        assert data["cleared"] == 1
        assert "mapping:Bad Entry:unknown" not in fake_redis.store
        assert "mapping:Bad Entry" not in fake_redis.store
