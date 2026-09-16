from datetime import datetime, timezone
import asyncpg
from fastapi import APIRouter, Depends, HTTPException, status, Request

from app.core.database import get_db_connection
from app.api.deps import get_current_user, check_task_access
from app.repositories.task_repo import TaskRepository
from app.repositories.team_repo import TeamRepository
from app.repositories.audit_repo import AuditRepository
from app.schemas.task import TaskCreate, TaskInDB, TaskUpdate, TaskFilterParams
from app.schemas.audit import AuditAction

router = APIRouter(prefix="/tasks", tags=["Tasks"])


@router.post("/create_task", status_code=status.HTTP_201_CREATED)
async def create_task(
    task_in: TaskCreate,
    request: Request,
    current_user: dict = Depends(get_current_user),
    db: asyncpg.Connection = Depends(get_db_connection)
):
    if task_in.deadline and task_in.deadline < datetime.now(timezone.utc):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Дедлайн не может быть в прошлом"
        )
    if task_in.team_id == 0:
        task_in.team_id = None
    if task_in.is_personal and task_in.team_id is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Задача не может быть личной и командной одновременно"
        )

    task_repo = TaskRepository(db)
    team_repo = TeamRepository(db)
    audit_repo = AuditRepository(db)

    # Проверяем команду, если задача привязана к команде
    if task_in.team_id is not None:
        team = await team_repo.get_by_id(task_in.team_id)
        if not team:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Такой команды не существует")

        role = await team_repo.get_user_role(task_in.team_id, current_user["id"])
        if not role:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Вы не состоите в данной команде")

    task_db = TaskInDB(
        owner_id=current_user["id"],
        team_id=task_in.team_id,
        title=task_in.title,
        description=task_in.description,
        deadline=task_in.deadline,
        is_personal=task_in.is_personal
    )

    new_task_id = await task_repo.create_task(task_db)
    if new_task_id is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Задача с таким названием уже существует"
        )

    await audit_repo.log_action(
        user_id=current_user["id"],
        username=current_user["username"],
        action=AuditAction.TASK_CREATED,
        target_type="task",
        target_id=new_task_id,
        target_name=task_db.title,
        ip_address=request.client.host,
        user_agent=request.headers.get("user-agent")
    )

    return {"status": "success", "task_id": new_task_id}


@router.delete("/delete_task/{task_id}")
async def delete_task(
    task_id: int,
    request: Request,
    current_user: dict = Depends(get_current_user),
    db: asyncpg.Connection = Depends(get_db_connection)
):
    task = await check_task_access(task_id, current_user["id"], db)

    task_repo = TaskRepository(db)
    audit_repo = AuditRepository(db)

    await audit_repo.log_action(
        user_id=current_user["id"],
        username=current_user["username"],
        action=AuditAction.TASK_DELETED,
        target_type="task",
        target_id=task_id,
        target_name=task["title"],
        ip_address=request.client.host,
        user_agent=request.headers.get("user-agent")
    )

    await task_repo.delete_task(task_id)
    return {"message": "Задача успешно удалена"}


@router.post("/{task_id}")
async def update_task(
    task_id: int,
    task_update: TaskUpdate,
    request: Request,
    current_user: dict = Depends(get_current_user),
    db: asyncpg.Connection = Depends(get_db_connection)
):
    task = await check_task_access(task_id, current_user["id"], db)

    completed_at = datetime.now(timezone.utc) if task_update.completed else None

    task_repo = TaskRepository(db)
    audit_repo = AuditRepository(db)

    result = await task_repo.update_task_version(
        task_id=task_id,
        description=task_update.description,
        completed=task_update.completed,
        completed_at=completed_at,
        current_version=task_update.version
    )

    if not result:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Не та версия задачи (конфликт изменений)"
        )

    await audit_repo.log_action(
        user_id=current_user["id"],
        username=current_user["username"],
        action=AuditAction.TASK_UPDATED,
        target_type="task",
        target_id=task_id,
        target_name=task["title"],
        ip_address=request.client.host,
        user_agent=request.headers.get("user-agent")
    )

    return {"message": "Задача успешно обновлена"}


@router.get("/")
async def get_my_tasks(
    filters: TaskFilterParams = Depends(),
    current_user: dict = Depends(get_current_user),
    db: asyncpg.Connection = Depends(get_db_connection)
):
    task_repo = TaskRepository(db)
    tasks = await task_repo.get_tasks_by_user(
        user_id=current_user["id"],
        completed=filters.completed,
        is_personal=filters.is_personal,
        team_id=filters.team_id,
        search=filters.search,
        limit=filters.limit,
        offset=filters.offset
    )
    return {
        "tasks": tasks,
        "limit": filters.limit,
        "offset": filters.offset
    }