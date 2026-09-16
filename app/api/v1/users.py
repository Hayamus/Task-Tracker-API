import asyncpg
from fastapi import APIRouter, Depends, HTTPException, status, Request
from app.core.database import get_db_connection
from app.core.security import verify_password
from app.api.deps import get_current_user
from app.repositories.user_repo import UserRepository
from app.repositories.audit_repo import AuditRepository
from app.schemas.audit import AuditAction

router = APIRouter(prefix="/users", tags=["Users"])


@router.get("/profile")
async def get_profile(
    current_user: dict = Depends(get_current_user),
    db: asyncpg.Connection = Depends(get_db_connection)
):
    user_repo = UserRepository(db)
    teams_count = await user_repo.get_user_teams_count(current_user["id"])

    return {
        "id": current_user["id"],
        "username": current_user["username"],
        "bio": current_user["bio"],
        "is_admin": current_user["is_admin"],
        "teams_count": teams_count
    }


@router.delete("/delete_acc")
async def delete_account(
    password: str,
    request: Request,
    current_user: dict = Depends(get_current_user),
    db: asyncpg.Connection = Depends(get_db_connection)
):
    if not verify_password(password, current_user["password"]):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Wrong password"
        )

    user_repo = UserRepository(db)
    audit_repo = AuditRepository(db)

    await audit_repo.log_action(
        user_id=current_user["id"],
        username=current_user["username"],
        action=AuditAction.USER_DELETED,
        target_type="user",
        target_id=current_user["id"],
        target_name=current_user["username"],
        ip_address=request.client.host,
        user_agent=request.headers.get("user-agent")
    )

    await user_repo.delete_user(current_user["id"])
    return {"status": "success"}