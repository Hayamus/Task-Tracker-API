import asyncpg, asyncio
DATABASE_URL='postgresql://myuser:mypassword@localhost:5432/mydatabase'
async def create_table():
    conn = await asyncpg.connect(DATABASE_URL)
    await conn.execute('''
CREATE TABLE IF NOT EXISTS refresh_tokens(
id SERIAL PRIMARY KEY,
user_id INT NOT NULL ,
refresh_token VARCHAR(255) NOT NULL UNIQUE,
expires_at TIMESTAMP NOT NULL,
created_at TIMESTAMP DEFAULT NOW())''')
    await conn.close()
asyncio.run(create_table())