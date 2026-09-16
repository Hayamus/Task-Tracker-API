import json
import asyncpg
from typing import Optional

class AnalyticsRepository:
    def __init__(self, db: asyncpg.Connection):
        self.db = db

    async def create_job(self, user_id: int, scope: str, params: dict) -> int:
        query = '''
        INSERT INTO analytics_jobs (user_id, scope, status, params, created_at)
        VALUES ($1, $2, 'pending', $3::jsonb, NOW())
        RETURNING id;
        '''
        return await self.db.fetchval(query, user_id, scope, json.dumps(params))

    async def get_latest_job(self, user_id: int, scope: str = 'user') -> Optional[asyncpg.Record]:
        query = """
            SELECT id, user_id, scope, status, params, result, started_at, finished_at, created_at
            FROM analytics_jobs
            WHERE user_id = $1 AND scope = $2
            ORDER BY created_at DESC
            LIMIT 1;
        """
        return await self.db.fetchrow(query, user_id, scope)

    async def get_job_by_id(self, job_id: int) -> Optional[asyncpg.Record]:
        query = "SELECT * FROM analytics_jobs WHERE id = $1;"
        return await self.db.fetchrow(query, job_id)

    async def set_job_running(self, job_id: int):
        query = """
            UPDATE analytics_jobs
            SET status = 'running', started_at = NOW()
            WHERE id = $1;
        """
        await self.db.execute(query, job_id)

    async def set_job_done(self, job_id: int, result: dict):
        query = """
            UPDATE analytics_jobs
            SET status = 'done', result = $2::jsonb, finished_at = NOW()
            WHERE id = $1;
        """
        await self.db.execute(query, job_id, json.dumps(result))

    async def set_job_failed(self, job_id: int, error_detail: str):
        query = """
            UPDATE analytics_jobs
            SET status = 'failed', result = $2::jsonb, finished_at = NOW()
            WHERE id = $1;
        """
        await self.db.execute(query, job_id, json.dumps({"error": error_detail}))