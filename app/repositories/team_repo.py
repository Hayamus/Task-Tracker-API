import asyncpg
from typing import Optional, List, Dict, Any
from app.schemas.user import UserRole

class TeamRepository:
    def __init__(self, conn: asyncpg.Connection):
        self.conn = conn

    async def exists_by_name(self, name: str) -> bool:
        row = await self.conn.fetchval("SELECT id FROM teams WHERE name = $1", name)
        return row is not None

    async def get_by_id(self, team_id: int) -> Optional[Dict[str, Any]]:
        row = await self.conn.fetchrow("SELECT id, name, description, owner_id FROM teams WHERE id = $1", team_id)
        return dict(row) if row else None

    async def create_team(self, owner_id: int, name: str, description: str) -> int:
        return await self.conn.fetchval(
            """
            INSERT INTO teams(owner_id, name, description)
            VALUES($1, $2, $3)
            RETURNING id
            """,
            owner_id, name, description
        )

    async def delete_team(self, team_id: int) -> None:
        await self.conn.execute("DELETE FROM teams WHERE id = $1", team_id)

    async def get_user_role(self, team_id: int, user_id: int) -> Optional[str]:
        return await self.conn.fetchval(
            "SELECT role FROM team_members WHERE team_id = $1 AND user_id = $2",
            team_id, user_id
        )

    async def add_member(self, team_id: int, user_id: int, role: str = UserRole.MEMBER.value) -> Optional[int]:
        return await self.conn.fetchval(
            """
            INSERT INTO team_members(team_id, user_id, role)
            VALUES($1, $2, $3)
            ON CONFLICT (team_id, user_id) DO NOTHING
            RETURNING id
            """,
            team_id, user_id, role
        )

    async def update_member_role(self, team_id: int, user_id: int, role: str) -> Optional[int]:
        return await self.conn.fetchval(
            """
            UPDATE team_members
            SET role = $1
            WHERE team_id = $2 AND user_id = $3
            RETURNING user_id
            """,
            role, team_id, user_id
        )

    async def remove_member(self, team_id: int, user_id: int) -> Optional[int]:
        return await self.conn.fetchval(
            """
            DELETE FROM team_members
            WHERE team_id = $1 AND user_id = $2
            RETURNING user_id
            """,
            team_id, user_id
        )