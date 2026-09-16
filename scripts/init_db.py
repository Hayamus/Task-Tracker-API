import asyncio
from pathlib import Path
import asyncpg
from app.core.config import settings

async def main():
    print("Подключение к базе данных PostgreSQL...")
    conn = await asyncpg.connect(dsn=settings.DATABASE_URL)
    
    sql_path = Path(__file__).parent / "init.sql"
    sql_script = sql_path.read_text(encoding="utf-8")
    
    print("Создание таблиц, индексов, триггеров...")
    await conn.execute(sql_script)
    
    await conn.close()
    print("Готово! Структура базы данных успешно создана.")

if __name__ == "__main__":
    asyncio.run(main())