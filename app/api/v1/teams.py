import asyncpg
from fastapi import APIRouter, Depends, HTTPException, status, Request
from app.core.database import get_db_connection
from app.core.security import verify_password
from app.api.deps import get_current_user, require_team_role
from app.repositories.team_repo import TeamRepository
from app.repositories.user_repo import UserRepository
from app.repositories.audit_repo import AuditRepository
from app.schemas.team import TeamCreate
from app.schemas.user import UserRole
from app.schemas.audit import AuditAction

router = APIRouter(prefix="/teams", tags=["Teams"])


@router.post("/create_team", status_code=status.HTTP_201_CREATED)
async def create_team(
    new_team: TeamCreate,
    request: Request,
    current_user: dict = Depends(get_current_user),
    db: asyncpg.Connection = Depends(get_db_connection)
):
    team_repo = TeamRepository(db)
    audit_repo = AuditRepository(db)

    if await team_repo.exists_by_name(new_team.name):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Команда с таким названием уже существует"
        )

    user_id = current_user["id"]
    new_team_id = await team_repo.create_team(user_id, new_team.name, new_team.description)
    await team_repo.add_member(new_team_id, user_id, UserRole.ADMIN.value)

    await audit_repo.log_action(
        user_id=user_id,
        username=current_user["username"],
        action=AuditAction.TEAM_CREATED,
        target_type="team",
        target_id=new_team_id,
        target_name=new_team.name,
        ip_address=request.client.host,
        user_agent=request.headers.get("user-agent")
    )

    return {"status": "success", "new_team_id": new_team_id}


@router.delete("/delete_team/{team_id}")
async def delete_team(
    team_id: int,
    password: str,
    request: Request,
    user: dict = Depends(require_team_role(["admin"])),
    db: asyncpg.Connection = Depends(get_db_connection)
):
    if not verify_password(password, user["password"]):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Wrong password")

    team_repo = TeamRepository(db)
    audit_repo = AuditRepository(db)

    team = await team_repo.get_by_id(team_id)
    team_name = team["name"] if team else None

    await audit_repo.log_action(
        user_id=user["id"],
        username=user["username"],
        action=AuditAction.TEAM_DELETED,
        target_type="team",
        target_id=team_id,
        target_name=team_name,
        ip_address=request.client.host,
        user_agent=request.headers.get("user-agent")
    )

    await team_repo.delete_team(team_id)
    return {"status": "success"}


@router.post("/{team_id}/members")
async def add_member(
    team_id: int,
    new_username: str,
    request: Request,
    user: dict = Depends(require_team_role(["admin", "moderator"])),
    db: asyncpg.Connection = Depends(get_db_connection)
):
    user_repo = UserRepository(db)
    team_repo = TeamRepository(db)
    audit_repo = AuditRepository(db)

    new_user = await user_repo.get_by_username(new_username)
    if not new_user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    result = await team_repo.add_member(team_id, new_user["id"])
    if result is None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Пользователь уже состоит в этой команде")

    team = await team_repo.get_by_id(team_id)
    await audit_repo.log_action(
        user_id=user["id"],
        username=user["username"],
        action=AuditAction.MEMBER_ADDED,
        target_type="team",
        target_id=team_id,
        target_name=team["name"] if team else None,
        changes={"id_new_member": new_user["id"]},
        ip_address=request.client.host,
        user_agent=request.headers.get("user-agent")
    )

    return {"message": f"Пользователь {new_username} успешно добавлен в команду"}


@router.post("/{team_id}/moderators")
async def add_moderator(
    team_id: int,
    user_to_moderator: str,
    request: Request,
    user: dict = Depends(require_team_role(["admin", "moderator"])),
    db: asyncpg.Connection = Depends(get_db_connection)
):
    user_repo = UserRepository(db)
    team_repo = TeamRepository(db)
    audit_repo = AuditRepository(db)

    target_user = await user_repo.get_by_username(user_to_moderator)
    if not target_user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    result = await team_repo.update_member_role(team_id, target_user["id"], UserRole.MODERATOR.value)
    if result is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Участник не состоит в данной команде")

    team = await team_repo.get_by_id(team_id)
    await audit_repo.log_action(
        user_id=user["id"],
        username=user["username"],
        action=AuditAction.MEMBER_ROLE_CHANGED,
        target_type="team",
        target_id=team_id,
        target_name=team["name"] if team else None,
        changes={"user_role_changed": target_user["username"]},
        ip_address=request.client.host,
        user_agent=request.headers.get("user-agent")
    )

    return {"message": f"Участник {user_to_moderator} успешно повышен до модератора"}


@router.delete("/{team_id}/members")
async def delete_member_from_team(
    team_id: int,
    user_to_delete: str,
    request: Request,
    user: dict = Depends(require_team_role(["admin"])),
    db: asyncpg.Connection = Depends(get_db_connection)
):
    user_repo = UserRepository(db)
    team_repo = TeamRepository(db)
    audit_repo = AuditRepository(db)

    target_user = await user_repo.get_by_username(user_to_delete)
    if not target_user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    result = await team_repo.remove_member(team_id, target_user["id"])
    if result is None:
        return {"message": "Пользователь не состоит в данной команде"}

    team = await team_repo.get_by_id(team_id)
    await audit_repo.log_action(
        user_id=user["id"],
        username=user["username"],
        action=AuditAction.MEMBER_REMOVED,
        target_type="team",
        target_id=team_id,
        target_name=team["name"] if team else None,
        changes={"user_removed": target_user["username"]},
        ip_address=request.client.host,
        user_agent=request.headers.get("user-agent")
    )

    return {"message": f"Пользователь {user_to_delete} успешно удален из команды"}


@router.post("/{team_id}/leave")
async def leave_team(
    team_id: int,
    request: Request,
    user: dict = Depends(require_team_role(["moderator", "member"])),
    db: asyncpg.Connection = Depends(get_db_connection)
):
    team_repo = TeamRepository(db)
    audit_repo = AuditRepository(db)

    await team_repo.remove_member(team_id, user["id"])
    team = await team_repo.get_by_id(team_id)

    await audit_repo.log_action(
        user_id=user["id"],
        username=user["username"],
        action=AuditAction.MEMBER_REMOVED,
        target_type="team",
        target_id=team_id,
        target_name=team["name"] if team else None,
        changes={"user_leaved": user["username"]},
        ip_address=request.client.host,
        user_agent=request.headers.get("user-agent")
    )

    return {"message": "Вы успешно покинули команду"}