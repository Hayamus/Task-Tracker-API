import asyncpg
from typing import Optional

class AttachmentRepository:
    def __init__(self, db: asyncpg.Connection):
        self.db = db

    async def create_attachment(
        self,
        task_id: int,
        owner_id: int,
        filename: str,
        size: int,
        content_type: str,
        storage_key: str
    ) -> int:
        query = """
            INSERT INTO attachments (task_id, owner_id, filename, size, content_type, storage_key, created_at)
            VALUES ($1, $2, $3, $4, $5, $6, NOW())
            RETURNING id;
        """
        return await self.db.fetchval(
            query,
            task_id,
            owner_id,
            filename,
            size,
            content_type,
            storage_key
        )

    async def get_by_id(self, attachment_id: int) -> Optional[asyncpg.Record]:
        query = "SELECT * FROM attachments WHERE id = $1;"
        return await self.db.fetchrow(query, attachment_id)

    async def delete(self, attachment_id: int) -> None:
        query = "DELETE FROM attachments WHERE id = $1;"
        await self.db.execute(query, attachment_id)