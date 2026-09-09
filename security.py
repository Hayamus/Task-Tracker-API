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
import hashlib

load_dotenv()

ACCESS_TOKEN_EXPIRES_MINUTES = 15
REFRESH_TOKEN_EXPIRES_MINUTES = 300
ALGORITHM='HS256'

oauth2_scheme = OAuth2PasswordBearer(tokenUrl='login')

async def get_user(username: str, db: asyncpg.Connection) -> Dict:
    user = await db.fetchrow('''
    SELECT id, password, username, is_admin, bio FROM users
    WHERE username=$1
    ''', username)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f'Пользователь "{username}" не найден')
    return dict(user)

async def check_user(username: str, db: asyncpg.Connection) -> bool:
    user_exist = await db.fetchrow('''
    SELECT username FROM users
    WHERE username=$1
    ''', username)
    if user_exist != None:
        return True
    else:
        return False

def hash_password(pwd: str) -> str:
    pwd_bytes = pwd.encode('utf-8')
    salt = bcrypt.gensalt()
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
    hashed_token = hashlib.sha256(token.encode()).hexdigest()
    await db.execute('''
    INSERT INTO refresh_tokens(id, user_id, expires_at)
    VALUES($1, $2, $3);
    ''', hashed_token, user_id, expire)
    return token

async def revoke_refresh_tokens(user_id: int, db: asyncpg.Connection) -> bool:
    revokes = await db.execute('''
    UPDATE refresh_tokens
    SET is_revoked = TRUE
    WHERE user_id=$1 AND is_revoked IS FALSE
    ''', user_id)
    if revokes != 'UPDATE 0':
        return True
    else:
        return False

async def revoke_single_refresh(raw_token: str, db: asyncpg.Connection) -> bool:
    token_hash = hashlib.sha256(raw_token.encode()).hexdigest()
    result = await db.execute('''
    UPDATE refresh_tokens SET is_revoked=TRUE WHERE id=$1 AND is_revoked IS FALSE
    ''', token_hash)
    if result == 'UPDATE 0':
        return False
    return True

def get_current_user(token: str = Depends(oauth2_scheme)) -> str:
    SECRET = os.getenv('SECRET_KEY')

    try:
        payload = jwt.decode(token, SECRET, ALGORITHM)
        username = payload.get('sub')
        return username
    
    except (jwt.ExpiredSignatureError, jwt.InvalidTokenError):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Токен истек или некорректен')

async def get_task(
        task_id: int,
        db: asyncpg.Connection
) -> Dict:
    result = await db.fetchrow('''
    SELECT id, owner_id, team_id, title, description, completed, created_at, updated_at, completed_at, version, deadline, is_personal
    FROM tasks 
    WHERE id=$1
    ''', task_id)
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail='Задача не найдена'
        )
    return dict(result)

async def check_task(
        user_id: int,
        task_id: int,
        db: asyncpg.Connection
) -> bool:
    task = await get_task(task_id, db)
    if user_id == task.get('owner_id'):
        return True
    if task.get('team_id') is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail='Вы не можете изменить данную задачу'
        )
    role = await db.fetchval('''
    SELECT role FROM team_members
    WHERE team_id=$1 AND user_id=$2;
    ''', task.get('team_id'), user_id)
    if not role:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail='Вы не являетесь участником команды с данной задачей'
        )
    if role not in ['admin', 'moderator']:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail='У вас нет права изменять данную задачу'
        )
    return True