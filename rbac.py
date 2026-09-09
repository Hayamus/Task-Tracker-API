from security import get_current_user, get_user, get_db_connection
from typing import List, Optional, Dict
from fastapi import Depends, Path, Query, Body, HTTPException, status
import asyncpg

async def get_user_role(
        user_id: int,
        team_id: int,
        db: asyncpg.Connection):
    role = await db.fetchval('''
    SELECT role FROM team_members WHERE user_id=$1 AND team_id=$2
    ''', user_id, team_id)
    return role

def require_team_role(required_roles: List[str]) -> Dict:
    async def dependency(
            payload: str = Depends(get_current_user),
            db: asyncpg.Connection = Depends(get_db_connection),
            team_id_path: Optional[int] = Path(alias="team_id"),
            team_id_query: Optional[int] = Query(None, alias="team_id"),
            team_id_body: Optional[int] = Body(None, embed=True),
    ):
        user = await get_user(payload, db)
        if not user:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail='User not found')

        team_id = team_id_path or team_id_query or team_id_body
        user_id = user.get('id')
        if team_id is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Укажите Team ID')

        role = await get_user_role(user_id, team_id, db)
        if not role:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail='Вы не состоите в данной команде')

        if role not in required_roles:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=f'Отказано в доступе. Требуются роли:{required_roles}, ваша роль:{role}')

        return user
    return dependency