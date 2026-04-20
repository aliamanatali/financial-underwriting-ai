"""
Cache observability and management endpoints.

Provides debug visibility into the expense normalization cache
(Redis + MongoDB) and allows targeted invalidation of stale entries.
No auth middleware exists in this codebase; these endpoints follow
the same open-access pattern as all other routes.
"""

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from typing import List, Optional
import json
import logging

logger = logging.getLogger(__name__)
router = APIRouter()


class CacheClearRequest(BaseModel):
    descriptions: List[str]


@router.get("/cache/mappings")
async def list_cache_mappings(
    prefix: str = Query(..., description="Description prefix to search for"),
    limit: int = Query(50, ge=1, le=500),
):
    """List cached expense mappings matching a description prefix.

    Searches both Redis and MongoDB. Returns matching entries with their
    cached category, confidence, and reasoning.
    """
    from app.db.redis import redis_client
    from app.db.mongodb import get_database
    from app.config import settings

    results = []

    # 1. Scan Redis for matching keys
    if redis_client.client:
        try:
            # SCAN with pattern — safe for production (non-blocking)
            pattern = f"mapping:{prefix}*"
            found = 0
            async for key in redis_client.client.scan_iter(match=pattern, count=100):
                if found >= limit:
                    break
                val = await redis_client.client.get(key)
                ttl = await redis_client.client.ttl(key)
                if val:
                    try:
                        parsed = json.loads(val)
                        results.append({
                            "source": "redis",
                            "key": key,
                            "ttl_seconds": ttl,
                            **parsed,
                        })
                        found += 1
                    except json.JSONDecodeError:
                        pass
        except Exception as e:
            logger.error(f"Redis scan error: {e}")

    # 2. Query MongoDB for matching entries
    if settings.use_mongodb:
        try:
            db = get_database()
            import re
            regex = re.compile(f"^{re.escape(prefix)}", re.IGNORECASE)
            cursor = db["expense_mappings"].find(
                {"original_text": {"$regex": regex}},
                projection={"_id": 0},
            ).limit(limit)

            async for doc in cursor:
                results.append({
                    "source": "mongodb",
                    "original_text": doc.get("original_text"),
                    "mapped_category": doc.get("mapped_category"),
                    "confidence": doc.get("confidence"),
                    "reasoning": doc.get("reasoning"),
                    "updated_at": doc.get("updated_at"),
                })
        except Exception as e:
            logger.error(f"MongoDB query error: {e}")

    return {"count": len(results), "entries": results}


@router.post("/cache/clear")
async def clear_cache_entries(request: CacheClearRequest):
    """Invalidate specific cache entries by description string.

    Removes matching entries from both Redis (new + legacy key formats)
    and MongoDB. Use the GET /cache/mappings endpoint first to identify
    entries to clear.
    """
    from app.services.normalization_service import NormalizationService

    cleared = []
    failed = []

    for desc in request.descriptions:
        try:
            await NormalizationService.invalidate_cache_entry(desc)
            cleared.append(desc)
        except Exception as e:
            logger.error(f"Failed to clear cache for '{desc}': {e}")
            failed.append({"description": desc, "error": str(e)})

    return {
        "cleared": len(cleared),
        "failed": len(failed),
        "cleared_descriptions": cleared,
        "errors": failed if failed else None,
    }


@router.get("/debug/cache-metrics")
async def get_cache_metrics():
    """Return in-memory cache hit/miss counters.

    Counters reset on process restart. Use to check inter-deal hit rate
    during observation. Not persistent — for quick diagnostics only.
    """
    from app.services.normalization_service import CACHE_METRICS

    total = CACHE_METRICS["hits"] + CACHE_METRICS["misses"]
    hit_rate = CACHE_METRICS["hits"] / total if total > 0 else 0.0

    return {
        **CACHE_METRICS,
        "total": total,
        "hit_rate": round(hit_rate, 4),
    }

