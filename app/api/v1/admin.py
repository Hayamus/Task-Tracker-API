from fastapi import APIRouter, Depends, status, HTTPException

from app.core.database import get_db_connection
from app.repositories.audit_repo import AuditRepository
from app.schemas.audit import AuditFilterParams
from app.api.deps import get_current_user

import asyncpg

router = APIRouter(prefix="/admin", tags=["Admin"])

@router.get("/audit_logs")
async def get_audit_logs(
    filters: AuditFilterParams = Depends(),
    current_user: dict = Depends(get_current_user),
    db: asyncpg.Connection = Depends(get_db_connection)
):
    audit_repo = AuditRepository(db)

    if not current_user["is_admin"]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    
    return await audit_repo.get_audit(
        user_id=filters.user_id,
        username=filters.username,
        action=filters.action,
        target_type=filters.target_type,
        target_id=filters.target_id,
        ip_address=filters.ip_address
    )