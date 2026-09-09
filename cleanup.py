import asyncio
import asyncpg
from datetime import datetime
from database import DATABASE_URL

async def cleanup_expired_tokens():
    conn = await asyncpg.connect(DATABASE_URL)
    try:
        deleted = await conn.execute('''
        DELETE FROM refresh_tokens
        WHERE expires_at < NOW() - INTERVAL '5 minutes' OR 
        is_revoked IS TRUE
        ''')
        if deleted != 'DELETE 0':
            count = int(deleted.split()[1])
            print(f'[{datetime.now()}] Cleaned up {count} expired tokens')
    except Exception as e:
        print(f'Cleanup error: {e}')
    finally:
        await conn.close()

async def run_cleanup_loop():
    while True:
        await cleanup_expired_tokens()
        await asyncio.sleep(300)