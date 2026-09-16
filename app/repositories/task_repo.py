import asyncpg
from datetime import datetime
from typing import Optional, List, Dict, Any
from app.schemas.task import TaskInDB

class TaskRepository:
    def __init__(self, conn: asyncpg.Connection):
        self.conn = conn

    async def get_by_id(self, task_id: int) -> Optional[Dict[str, Any]]:
        row = await self.conn.fetchrow(
            """
            SELECT id, owner_id, team_id, title, description, completed, 
                   created_at, updated_at, completed_at, version, deadline, is_personal
            FROM tasks
            WHERE id = $1
            """,
            task_id
        )
        return dict(row) if row else None

    async def create_task(self, task: TaskInDB) -> Optional[int]:
        return await self.conn.fetchval(
            """
            INSERT INTO tasks(owner_id, team_id, title, description, deadline, is_personal)
            VALUES($1, $2, $3, $4, $5, $6)
            ON CONFLICT(title) DO NOTHING
            RETURNING id
            """,
            task.owner_id, task.team_id, task.title, task.description, task.deadline, task.is_personal
        )

    async def delete_task(self, task_id: int) -> None:
        await self.conn.execute("DELETE FROM tasks WHERE id = $1", task_id)

    async def update_task_version(
        self,
        task_id: int,
        description: Optional[str],
        completed: bool,
        completed_at: Optional[datetime],
        current_version: int
    ) -> Optional[int]:
        """Оптимистическая блокировка через инкремент версии"""
        return await self.conn.fetchval(
            """
            UPDATE tasks
            SET description = $1, completed = $2, updated_at = NOW(), completed_at = $3, version = $4
            WHERE id = $5 AND version = $6
            RETURNING id
            """,
            description, completed, completed_at, current_version + 1, task_id, current_version
        )

    async def get_tasks_by_user(
        self,
        user_id: int,
        completed: Optional[bool] = None,
        is_personal: Optional[bool] = None,
        team_id: Optional[int] = None,
        search: Optional[str] = None,
        limit: int = 20,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        query = [
            """
            SELECT id, team_id, title, description, completed, 
                   created_at, updated_at, completed_at, version, deadline, is_personal
            FROM tasks
            WHERE owner_id = $1
            """
        ]
        params: List[Any] = [user_id]
        param_idx = 2

        if completed is not None:
            query.append(f"AND completed = ${param_idx}")
            params.append(completed)
            param_idx += 1

        if is_personal is not None:
            query.append(f"AND is_personal = ${param_idx}")
            params.append(is_personal)
            param_idx += 1

        if team_id is not None:
            query.append(f"AND team_id = ${param_idx}")
            params.append(team_id)
            param_idx += 1

        if search:
            query.append(f"AND title ILIKE ${param_idx}")
            params.append(f"%{search}%")
            param_idx += 1

        query.append(f"ORDER BY created_at DESC LIMIT ${param_idx} OFFSET ${param_idx + 1}")
        params.extend([limit, offset])

        full_sql = " ".join(query)
        rows = await self.conn.fetch(full_sql, *params)
        return [dict(row) for row in rows]