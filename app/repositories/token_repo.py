import asyncpg
from datetime import datetime
from typing import Optional, Dict, Any

class TokenRepository:
    def __init__(self, conn: asyncpg.Connection):
        self.conn = conn

    async def create_refresh_token(self, token_hash: str, user_id: int, expires_at: datetime) -> None:
        await self.conn.execute(
            """
            INSERT INTO refresh_tokens(id, user_id, expires_at)
            VALUES($1, $2, $3)
            """,
            token_hash, user_id, expires_at
        )

    async def get_refresh_token(self, token_hash: str) -> Optional[Dict[str, Any]]:
        row = await self.conn.fetchrow(
            """
            SELECT user_id, expires_at, is_revoked
            FROM refresh_tokens
            WHERE id = $1
            """,
            token_hash
        )
        return dict(row) if row else None

    async def revoke_single_refresh(self, token_hash: str) -> bool:
        result = await self.conn.execute(
            """
            UPDATE refresh_tokens 
            SET is_revoked = TRUE 
            WHERE id = $1 AND is_revoked IS FALSE
            """,
            token_hash
        )
        return result != "UPDATE 0"

    async def revoke_all_user_tokens(self, user_id: int) -> bool:
        result = await self.conn.execute(
            """
            UPDATE refresh_tokens
            SET is_revoked = TRUE
            WHERE user_id = $1 AND is_revoked IS FALSE
            """,
            user_id
        )
        return result != "UPDATE 0"