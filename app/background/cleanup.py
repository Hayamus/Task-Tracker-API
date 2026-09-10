import asyncio
from datetime import datetime
from app.core.database import db_pool

async def cleanup_expired_tokens() -> None:
    if db_pool is None:
        return

    async with db_pool.acquire() as conn:
        try:
            deleted = await conn.execute("""
                DELETE FROM refresh_tokens
                WHERE expires_at < NOW() - INTERVAL '5 minutes' 
                   OR is_revoked IS TRUE
            """)
            if deleted != "DELETE 0":
                count = int(deleted.split()[1])
                print(f"[{datetime.now()}] Cleaned up {count} expired tokens")

            deleted = await conn.execute("""
                DELETE FROM audit_logs
                WHERE created_at < NOW() - INTERVAL '10 minutes'
            """)
            if deleted != "DELETE 0":
                count = int(deleted.split()[1])
                print(f"[{datetime.now()}] Cleaned up {count} old audit logs")

        except Exception as e:
            print(f"Cleanup error: {e}")

async def run_cleanup_loop() -> None:
    while True:
        await cleanup_expired_tokens()
        await asyncio.sleep(300)