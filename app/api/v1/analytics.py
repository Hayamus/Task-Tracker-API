from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status

from app.core.database import get_db_connection
from app.api.deps import get_current_user
from app.repositories.analytics_repo import AnalyticsRepository
from app.schemas.analytics import AnalyticsComputeRequest, AnalyticsJobResponse
from app.background.analytics_worker import compute_analytics_job

router = APIRouter(prefix="/todos/analytics", tags=["Analytics"])

def validate_timezone(tz_name: str) -> None:
    try:
        ZoneInfo(tz_name)
    except (ZoneInfoNotFoundError, ValueError, Exception):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Некорректная таймзона: '{tz_name}'. Пример корректной: 'Europe/Kyiv', 'UTC'"
        )

@router.post("/compute", response_model=AnalyticsJobResponse, status_code=status.HTTP_202_ACCEPTED)
async def compute_analytics(
    request: AnalyticsComputeRequest,
    current_user: dict = Depends(get_current_user),
    db: asyncpg.Connection = Depends(get_db_connection)
):
    validate_timezone(request.timezone)

    repo = AnalyticsRepository(db)
    
    job_id = await repo.create_job(
        user_id=current_user["id"],
        scope=request.scope,
        params={"timezone": request.timezone, "scope": request.scope}
    )

    compute_analytics_job.delay(job_id)

    return AnalyticsJobResponse(
        job_id=job_id,
        status="pending",
        message="Расчёт аналитики поставлен в очередь"
    )

@router.get("")
async def get_analytics(
    response: Response,
    scope: str = Query(default="user", description="Scope аналитики"),
    current_user: dict = Depends(get_current_user),
    db: asyncpg.Connection = Depends(get_db_connection)
):
    repo = AnalyticsRepository(db)
    job = await repo.get_latest_job(user_id=current_user["id"], scope=scope)

    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Для вас ещё не запускался расчёт аналитики. Вызовите сначала POST /todos/analytics/compute"
        )

    if job["status"] in ["pending", "running"]:
        response.status_code = status.HTTP_202_ACCEPTED
        return {
            "job_id": job["id"],
            "status": job["status"],
            "message": "Расчёт всё ещё выполняется. Повторите запрос позже."
        }

    if job["status"] == "failed":
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ошибка при расчёте аналитики: {job['result']}"
        )

    return {
        "job_id": job["id"],
        "status": job["status"],
        "finished_at": job["finished_at"],
        "result": job["result"]
    }