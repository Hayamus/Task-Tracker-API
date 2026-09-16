import asyncpg
from typing import Optional, AsyncGenerator
from app.core.config import settings

db_pool: Optional[asyncpg.Pool] = None

async def init_db() -> None:
    global db_pool
    db_pool = await asyncpg.create_pool(
        dsn=settings.DATABASE_URL,
        min_size=5,
        max_size=20
    )
    print("Database connection pool initialized")

async def close_db() -> None:
    global db_pool
    if db_pool:
        await db_pool.close()
        print("Database connection pool closed")

async def get_db_connection() -> AsyncGenerator[asyncpg.Connection, None]:
    if db_pool is None:
        raise RuntimeError("Database pool is not initialized")
        
    async with db_pool.acquire() as conn:
        yield conn