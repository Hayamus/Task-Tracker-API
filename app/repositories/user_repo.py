import asyncpg
from typing import Optional, Dict, Any
from app.schemas.user import UserInDB

class UserRepository:
    def __init__(self, conn: asyncpg.Connection):
        self.conn = conn

    async def get_by_username(self, username: str) -> Optional[Dict[str, Any]]:
        row = await self.conn.fetchrow(
            "SELECT id, password, username, is_admin, bio FROM users WHERE username = $1",
            username
        )
        return dict(row) if row else None

    async def get_by_id(self, user_id: int) -> Optional[Dict[str, Any]]:
        row = await self.conn.fetchrow(
            "SELECT id, password, username, is_admin, bio FROM users WHERE id = $1",
            user_id
        )
        return dict(row) if row else None

    async def exists_by_username(self, username: str) -> bool:
        row = await self.conn.fetchrow("SELECT id FROM users WHERE username = $1", username)
        return row is not None

    async def create_user(self, user: UserInDB) -> int:
        user_id = await self.conn.fetchval(
            """
            INSERT INTO users(username, password, bio, is_admin)
            VALUES ($1, $2, $3, $4)
            RETURNING id
            """,
            user.username, user.password, user.bio, user.is_admin
        )
        return user_id

    async def delete_user(self, user_id: int) -> None:
        await self.conn.execute("DELETE FROM users WHERE id = $1", user_id)

    async def get_user_teams_count(self, user_id: int) -> int:
        return await self.conn.fetchval(
            "SELECT COUNT(*) FROM team_members WHERE user_id = $1",
            user_id
        )