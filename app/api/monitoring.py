import os
import time
import redis.asyncio as aioredis
from fastapi import APIRouter, status
from fastapi.responses import JSONResponse, Response

from app.core.config import settings
from app.core import database
from app.core.metrics import get_metrics_exposition

router = APIRouter(tags=["Monitoring"])


@router.get("/health", status_code=status.HTTP_200_OK)
async def health_check():
    checks = {}
    is_healthy = True

    db_start = time.perf_counter()
    try:
        if database.db_pool is None:
            raise RuntimeError("Database pool not initialized")
        async with database.db_pool.acquire() as conn:
            await conn.fetchval("SELECT 1;")
        db_duration = round((time.perf_counter() - db_start) * 1000, 2)
        checks["database"] = {"status": "healthy", "latency_ms": db_duration}
    except Exception as e:
        is_healthy = False
        checks["database"] = {"status": "unhealthy", "error": str(e)}

    redis_url = getattr(settings, "REDIS_URL", "redis://localhost:6379/0")
    redis_start = time.perf_counter()
    try:
        r = aioredis.from_url(redis_url, socket_timeout=2.0)
        await r.ping()
        await r.aclose()
        redis_duration = round((time.perf_counter() - redis_start) * 1000, 2)
        checks["broker"] = {"status": "healthy", "latency_ms": redis_duration}
    except Exception as e:
        is_healthy = False
        checks["broker"] = {"status": "unhealthy", "error": str(e)}

    try:
        upload_dir = getattr(settings, "UPLOAD_DIR", "uploads")
        exists = os.path.exists(upload_dir)
        writable = os.access(upload_dir, os.W_OK) if exists else False

        if exists and writable:
            checks["storage"] = {"status": "healthy", "writable": True}
        else:
            is_healthy = False
            checks["storage"] = {
                "status": "unhealthy",
                "exists": exists,
                "writable": writable
            }
    except Exception as e:
        is_healthy = False
        checks["storage"] = {"status": "unhealthy", "error": str(e)}

    response_data = {
        "status": "healthy" if is_healthy else "unhealthy",
        "timestamp": time.time(),
        "dependencies": checks
    }

    http_status = status.HTTP_200_OK if is_healthy else status.HTTP_503_SERVICE_UNAVAILABLE
    return JSONResponse(status_code=http_status, content=response_data)


@router.get("/metrics")
async def metrics() -> Response:
    return get_metrics_exposition()