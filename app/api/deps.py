from typing import List, Optional, Dict, Any
import asyncpg
import jwt
from fastapi import Depends, HTTPException, status, Path, Query, Body
from fastapi.security import OAuth2PasswordBearer

from app.core.database import get_db_connection
from app.core.security import decode_access_token
from app.repositories.user_repo import UserRepository
from app.repositories.team_repo import TeamRepository
from app.repositories.task_repo import TaskRepository

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: asyncpg.Connection = Depends(get_db_connection)
) -> Dict[str, Any]:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Не удалось подтвердить учетные данные",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        payload = decode_access_token(token)
        username: Optional[str] = payload.get("sub")
        token_type: Optional[str] = payload.get("type")
        
        if username is None or token_type != "access":
            raise credentials_exception
            
    except (jwt.ExpiredSignatureError, jwt.InvalidTokenError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Токен истек или некорректен",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_repo = UserRepository(db)
    user = await user_repo.get_by_username(username)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f'Пользователь "{username}" не найден'
        )
        
    return user

def require_team_role(required_roles: List[str]):
    async def dependency(
        current_user: Dict[str, Any] = Depends(get_current_user),
        db: asyncpg.Connection = Depends(get_db_connection),
        team_id_path: Optional[int] = Path(alias="team_id"),
        team_id_query: Optional[int] = Query(None, alias="team_id"),
        team_id_body: Optional[int] = Body(None, embed=True),
    ) -> Dict[str, Any]:
        team_id = team_id_path or team_id_query or team_id_body
        if team_id is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Укажите Team ID"
            )

        team_repo = TeamRepository(db)
        role = await team_repo.get_user_role(team_id, current_user["id"])
        
        if not role:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Вы не состоите в данной команде"
            )

        if role not in required_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Отказано в доступе. Требуются роли: {required_roles}, ваша роль: {role}"
            )

        return current_user

    return dependency

async def check_task_access(
    task_id: int,
    user_id: int,
    db: asyncpg.Connection
) -> Dict[str, Any]:
    task_repo = TaskRepository(db)
    task = await task_repo.get_by_id(task_id)
    
    if not task:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Задача не найдена"
        )

    if task["owner_id"] == user_id:
        return task

    if task["team_id"] is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Вы не можете изменить чужую личную задачу"
        )

    team_repo = TeamRepository(db)
    role = await team_repo.get_user_role(task["team_id"], user_id)
    
    if not role:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Вы не являетесь участником команды с данной задачей"
        )
        
    if role not in ["admin", "moderator"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="У вас нет права изменять задачи в этой команде"
        )

    return task