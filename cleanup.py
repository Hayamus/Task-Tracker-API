import asyncio
import asyncpg
from datetime import datetime
from database import DATABASE_URL

async def cleanup_expired_tokens():
    conn = await asyncpg.connect(DATABASE_URL)
    try:
        deleted = await conn.execute('''
        DELETE FROM refresh_tokens
        WHERE expires_at < NOW() - INTERVAL "5 minutes"''')
        if deleted != 'DELETE 0':
            print(f'[{datetime.now()}] Cleaned up {deleted} expired tokens')
    except Exception as e:
        print(f'Cleanup error: {e}')
    finally:
        await conn.close()

async def run_cleanup_loop():
    while True:
        await cleanup_expired_tokens()
        await asyncio.sleep(300)