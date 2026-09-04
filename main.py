from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, HTTPException, status, Response, Cookie
from fastapi.security import OAuth2PasswordRequestForm
from database import get_db_connection
import asyncio
import asyncpg
from cleanup import run_cleanup_loop
from models import User, UserCreate, UserRole, UserInDB
from security import check_user, hash_password, verify, create_access_token, create_refresh_token, oauth2_scheme, get_current_user, revoke_single_refresh, revoke_refresh_tokens
import uvicorn
import os
import hashlib

IS_PRODUCTION = os.getenv('ENVIRONMENT') == 'production'

@asynccontextmanager
async def lifespan(app: FastAPI):
    cleanup_task = asyncio.create_task(run_cleanup_loop())
    yield
    cleanup_task.cancel()
    try:
        await cleanup_task
    except asyncio.CancelledError:
        pass

app = FastAPI(lifespan=lifespan)

@app.post('/register', status_code=status.HTTP_201_CREATED)
async def reg_user(user: UserCreate,
                   db: asyncpg.Connection = Depends(get_db_connection)
                   ):
    if await check_user(user.username, db):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT,
                            detail=f'Пользователь с никнеймом "{user.username}" уже существует')
    
    user_dict = user.model_dump()
    user_dict['password'] = hash_password(user_dict['password'])
    new_user = UserInDB(**user_dict)

    await db.execute('''
    INSERT INTO users(username, password, bio, user_role)
    VALUES ($1, $2, $3, $4)
    ''', new_user.username, new_user.password, new_user.bio, new_user.role)

    return {'status': 'success'}

@app.post('/login')
async def login(response: Response,
                user: OAuth2PasswordRequestForm = Depends(),
                db: asyncpg.Connection = Depends(get_db_connection)
                ):
    if not await check_user(user.username, db):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail='Неверный логин или пароль',
                            headers={'WWW-Authenticate': 'Bearer'})
    
    hashed_pwd = await db.fetchval('''
    SELECT password FROM users WHERE username=$1
    ''', user.username)
    if not verify(user.password, hashed_pwd):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail='Неверный логин или пароль',
                            headers={'WWW-Authenticate': 'Bearer'})

    user_id = await db.fetchval('''
    SELECT id FROM users WHERE username=$1
    ''', user.username)

    access_token = create_access_token({'sub': user.username})
    refresh_token = await create_refresh_token(user_id, db)

    response.set_cookie(
        key='refresh_token',
        value=refresh_token,
        httponly=True,
        secure=IS_PRODUCTION,
        samesite='lax',
        max_age=604800,
        path='/'
    )

    return {
        'access_token': access_token,
        'token_type': 'bearer',
        'message': 'Вход выполнен успешно'
    }

@app.post('/auth/logout')
async def logout(
    response: Response,
    refresh_token: str | None = Cookie(default=None),
    db: asyncpg.Connection = Depends(get_db_connection),
    ):
    if not refresh_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='No refresh token')

    result = await revoke_single_refresh(refresh_token, db)
    if not result:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Токен не найден')
    response.delete_cookie('refresh_token')

    return {'message':'Logged out successfully'}

@app.post('/auth/logout_all_sessions')
async def logout_all(
    response: Response,
    username: str = Depends(get_current_user),
    refresh_token: str | None = Cookie(default=None),
    db: asyncpg.Connection = Depends(get_db_connection)
    ):
    if not refresh_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='No refresh token')

    user_id = await db.fetchval('''
        SELECT id FROM users WHERE username=$1
        ''', username)
    if user_id == None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail='User not found')

    result = await revoke_refresh_tokens(user_id, db)
    if not result:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Токены не найдены')

    response.delete_cookie('refresh_token')

    return {'message': 'All sessions is closed'} 

@app.post('/refresh')
async def refresh(
    response: Response,
    refresh_token: str | None = Cookie(default=None),
    db: asyncpg.Connection = Depends(get_db_connection)
):
    if not refresh_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='No refresh token')

    token_hash = hashlib.sha256(refresh_token.encode()).hexdigest()
    row = await db.fetchrow('''
    SELECT user_id, expires_at, is_revoked
    FROM refresh_tokens
    WHERE id=$1
    ''', token_hash)
    if not row: 
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Invalid refresh token')

    if row['is_revoked'] is True:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='Token revoked')

    user_id = row['user_id']
    username = await db.fetchval('''
    SELECT username FROM users WHERE id=$1
    ''', user_id)
    new_access_token = create_access_token({'sub': username})
    new_refresh_token = await create_refresh_token(user_id, db)
    response.delete_cookie('refresh_token')
    response.set_cookie(
            key='refresh_token',
            value=new_refresh_token,
            httponly=True,
            secure=IS_PRODUCTION,
            samesite='lax',
            max_age=604800,
            path='/'
        )
    return {
        'access_token': new_access_token,
        'token_type': 'bearer'
        }

if __name__ == '__main__':
    uvicorn.run('main:app',
                port=8000,
                host='127.0.0.1',
                reload=True)
