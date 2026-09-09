from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, HTTPException, status, Response, Cookie
from fastapi.security import OAuth2PasswordRequestForm
from database import get_db_connection
import asyncio
from typing import Dict, Optional
import asyncpg
from cleanup import run_cleanup_loop
from models import User, UserCreate, UserRole, UserInDB, TeamCreate, TaskCreate, TaskInDB, TaskUpdate
from security import check_task, check_user, hash_password, verify, create_access_token, create_refresh_token, oauth2_scheme, get_user, get_current_user, revoke_single_refresh, revoke_refresh_tokens
import uvicorn
from rbac import require_team_role
import os
import hashlib
from datetime import datetime, timezone

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
    INSERT INTO users(username, password, bio, is_admin)
    VALUES ($1, $2, $3, $4)
    ''', new_user.username, new_user.password, new_user.bio, new_user.is_admin)

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

@app.get('/profile')
async def get_info(
    username: str = Depends(get_current_user),
    db: asyncpg.Connection = Depends(get_db_connection)
):
    user = await get_user(username, db)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail='User not found'
        )
    count_teams = await db.fetchval('''
    SELECT COUNT(*) FROM team_members WHERE user_id=$1
    ''', user.get('id'))

    return {
        'id': user.get('id'),
        'username': user.get('username'),
        'bio': user.get('bio'),
        'is_admin': user.get('is_admin'),
        'teams_count': count_teams
    }

@app.post('/teams/create_team', status_code=status.HTTP_201_CREATED)
async def create_team(
    new_team: TeamCreate,
    db: asyncpg.Connection = Depends(get_db_connection),
    username: str = Depends(get_current_user)
):
    check = await db.fetchval('''
    SELECT id FROM teams WHERE name=$1;
    ''', new_team.name)
    if check is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail='Команда с таким названием уже существует'
        )
    
    user = await get_user(username, db)
    user_id = user.get('id')

    new_team_id = await db.fetchval('''
    INSERT INTO teams(owner_id, name, description) VALUES($1, $2, $3) RETURNING id
    ''', user_id, new_team.name, new_team.description)
    await db.execute('''
    INSERT INTO team_members(team_id, user_id, role) VALUES($1, $2, $3)
    ''', new_team_id, user_id, UserRole.ADMIN)

    return {
        'status': 'success',
        'new_team_id': new_team_id
    }

@app.delete('/users/delete_acc')
async def del_acc(
    password: str,
    username: str = Depends(get_current_user), 
    db: asyncpg.Connection = Depends(get_db_connection)
    ):
    user = await get_user(username, db)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail='User not found'
            )
    if not verify(password, user.get('password')):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail='Wrong password'
        )
    await db.execute('''
    DELETE FROM users WHERE id=$1
    ''', user.get('id'))

    return {
        'status': 'success'
    }

@app.delete('/teams/delete_team/{team_id}')
async def del_team(
    team_id: int,
    password: str,
    user: Dict = Depends(require_team_role(['admin'])),
    db: asyncpg.Connection = Depends(get_db_connection)
):
    
    if not verify(password, user.get('password')):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail='Wrong password'
        )

    await db.execute('''
    DELETE FROM teams WHERE id=$1
    ''', team_id)

    return {
        'status': 'success' 
    }

@app.post('/teams/{team_id}/members')
async def add_member(
    team_id: int,
    new_username: str,
    user: Dict = Depends(require_team_role(['admin', 'moderator'])),
    db: asyncpg.Connection = Depends(get_db_connection)
):
    new_user = await get_user(new_username, db)
    if not new_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail='User not found'
        )

    result = await db.fetchval('''
    INSERT INTO team_members(team_id, user_id) VALUES($1, $2)
    ON CONFLICT (team_id, user_id) DO NOTHING
    RETURNING id;
    ''', team_id, new_user.get('id'))

    if result is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail='Пользователь уже состоит в этой команде'
        )
    
    return {
        'message': f'Пользователь {new_username} успешно добавлен в команду'
    }

@app.post('/teams/{team_id}/moderators')
async def add_moderator(
    team_id: int,
    user_to_moderator: str,
    current_user: Dict = Depends(require_team_role(['admin', 'moderator'])),
    db: asyncpg.Connection = Depends(get_db_connection)
):
    user = await get_user(user_to_moderator, db)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail='User not found'
        )
    
    result = await db.fetchval('''
    UPDATE team_members
    SET role = 'moderator'
    WHERE team_id = $1 AND user_id = $2
    RETURNING user_id;
    ''', team_id, user.get('id'))

    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail='Участник не состоит в данной команде'
        )

    return {
        'message': f'Участник {user_to_moderator} успешно повышен до модератора'
    }

@app.delete('/teams/{team_id}/members')
async def del_member_from_team(
    team_id: int,
    user_to_delete: str,
    current_user: Dict = Depends(require_team_role(['admin'])),
    db: asyncpg.Connection = Depends(get_db_connection)
):
    user = await get_user(user_to_delete, db)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail='User not found'
        )

    result = await db.fetchval('''
    DELETE FROM team_members
    WHERE team_id=$1 AND user_id=$2
    RETURNING user_id;
    ''', team_id, user.get('id'))

    if result is None:
        return{
            'message': 'Пользователь не состоит в данной команде'
        }
    return{
        'message': f'Пользователь {user_to_delete} успешно удален из команды'
    }

@app.post('/teams/{team_id}/leave')
async def leave_from_team(
    team_id: int,
    user: Dict = Depends(require_team_role(['moderator', 'member'])),
    db: asyncpg.Connection = Depends(get_db_connection)
):
    await db.execute('''
    DELETE FROM team_members
    WHERE team_id=$1 AND user_id=$2;
    ''', team_id, user.get('id'))

    return {
        'message': 'Вы успешно покинули команду'
    }

@app.post('/tasks/create_task')
async def create_task(
    task: TaskCreate,
    username: str = Depends(get_current_user),
    db: asyncpg.Connection = Depends(get_db_connection)
):
    if task.deadline and task.deadline < datetime.now(timezone.utc):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail='Дедлайн не может быть в прошлом'
        )
    if task.team_id == 0:
        task.team_id = None
    if task.is_personal and task.team_id is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail='Задача не может быть личной и командной одновременно'
        )

    user = await get_user(username, db)
    new_task = TaskInDB(
            owner_id=user.get('id'),
            team_id=task.team_id,
            title=task.title,
            description=task.description,
            deadline=task.deadline,
            is_personal=task.is_personal
        )
    
    if task.team_id is not None:
        result = await db.fetchval('''
        SELECT id FROM teams WHERE id=$1
        ''', task.team_id)
        if not result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail='Такой команды не существует'
            )
        
        result = await db.fetchval('''
        SELECT id FROM team_members WHERE team_id=$1 AND user_id=$2
        ''', task.team_id, user.get('id'))
        if not result:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail='Вы не состоите в данной команде'
            )
        pass
    result = await db.fetchval('''
    INSERT INTO tasks(owner_id, team_id, title, description, deadline, is_personal)
    VALUES($1, $2, $3, $4, $5, $6)
    ON CONFLICT(title) DO NOTHING
    RETURNING id;
    ''', new_task.owner_id, new_task.team_id, new_task.title, new_task.description, new_task.deadline, new_task.is_personal)

    if result is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail='Задача с таким названием уже существует'
        )

    return {
        'status': 'success'
    }

@app.delete('/tasks/delete_task/{task_id}')
async def del_task(
    task_id: int,
    username: str = Depends(get_current_user),
    db: asyncpg.Connection = Depends(get_db_connection)
):
    user =  await get_user(username, db)
    if await check_task(
        user.get('id'),
        task_id,
        db
    ):
        await db.execute('''
        DELETE FROM tasks WHERE id=$1
        ''', task_id)

        return {
            'message': 'Задача успешно удалена'
        }

@app.post('/tasks/{task_id}')
async def update_task(
    task_id: int,
    task: TaskUpdate,
    username: str = Depends(get_current_user),
    db: asyncpg.Connection = Depends(get_db_connection)
):
    user = await get_user(username, db)
    completed_at = None
    if await check_task(
        user.get('id'),
        task_id,
        db
    ):
        if task.completed:
            completed_at = datetime.now()
        result = await db.fetchval('''
        UPDATE tasks
        SET description = $1, completed = $2, updated_at = NOW(), completed_at = $3, version = $4
        WHERE id = $5 AND version = $6
        RETURNING id;
        ''', task.description, task.completed, completed_at, task.version+1, task_id, task.version)
        if not result: 
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail='Не та версия задачи'
            )
        return {
            'message': 'Задача успешно обновлена'
        }

@app.get('/tasks/{user_id}')
async def get_tasks_by_user(
    username: str = Depends(get_current_user),
    db: asyncpg.Connection = Depends(get_db_connection)
):
    user = await get_user(username, db)
    result = await db.fetch('''
    SELECT id, team_id, title, description, completed
    FROM tasks
    WHERE owner_id=$1
    ''', user.get('id'))
    return {'tasks': result}

if __name__ == '__main__':
    uvicorn.run('main:app',
                port=8000,
                host='127.0.0.1',
                reload=True)
