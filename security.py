import jwt
import datetime
from fastapi import Depends, status, HTTPException
from fastapi.security import OAuth2PasswordBearer
from typing import Dict
import os
from dotenv import load_dotenv
import bcrypt
import asyncpg
from database import get_db_connection
import uuid

load_dotenv()

ACCESS_TOKEN_EXPIRES_MINUTES = 15
REFRESH_TOKEN_EXPIRES_MINUTES = 300
ALGORITHM='HS256'

async def get_user(username: str, db: asyncpg.Connection) -> Dict:
    user = await db.fetchrow('''
    SELECT id, password, username, user_role FROM users
    WHERE username=$1
    ''', username)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f'Пользователь "{username}" не найден')
    return dict(user)

def hash_password(pwd: str):
    pwd_bytes = pwd.encode('utf-8')
    salt = bcrypt.gensalt
    return bcrypt.hashpw(pwd_bytes, salt).decode('utf-8')

def verify(plain_pwd: str, hashed_pwd: str) -> bool:
    plain_bytes = plain_pwd.encode('utf-8')
    hashed_bytes = hashed_pwd.encode('utf-8')
    return bcrypt.checkpw(plain_bytes, hashed_bytes)

def create_access_token(data: Dict):
    to_encode = data.copy()
    expire = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(minutes=ACCESS_TOKEN_EXPIRES_MINUTES)
    to_encode.update({'exp': expire, 'type':'access'})
    SECRET = os.getenv('SECRET_KEY')
    return jwt.encode(to_encode, SECRET, ALGORITHM)

async def create_refresh_token(user_id: int, db: asyncpg.Connection):
    token = str(uuid.uuid4())
    expire = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(minutes=REFRESH_TOKEN_EXPIRES_MINUTES)
    salt = bcrypt.gensalt()
    token_bytes = token.encode('utf-8')
    hashed_token = bcrypt.hashpw(token_bytes, salt)
    update = await db.execute('''
    INSERT INTO refresh_tokens(id, user_id, expires_at)
    VALUES($1, $2, $3);
    ''', hashed_token, user_id, expire)
    return token

async def revoke_refresh_tokens(user_id: int, db: asyncpg.Connection) -> bool:
    revokes = await db.execute('''
    UPDATE refresh_tokens
    SET is_revoked = TRUE
    WHERE user_id=$1
    ''', user_id)
    if revokes != 'UPDATE 0':
        return True
    else:
        return False

async def revoke_single_refresh(user_id: int, raw_token: str, db: asyncpg.Connection) -> bool:
    tokens = await db.fetch('''
    SELECT id FROM refresh_tokens WHERE user_id = $1 AND is_revoked IS FALSE
    ''', user_id)
    for token in tokens:
        if bcrypt.checkpw(raw_token.encode('utf-8'), token['id'].encode('utf-8')):
            await db.execute(
                '''UPDATE refresh_tokens SET is_revoked=TRUE WHERE id = $1''',
                token['id']
            )
            return True
    return False