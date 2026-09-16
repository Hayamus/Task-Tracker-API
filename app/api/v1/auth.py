import asyncpg
from fastapi import APIRouter, Depends, HTTPException, status, Response, Request, Cookie
from fastapi.security import OAuth2PasswordRequestForm

from app.core.config import settings
from app.core.database import get_db_connection
from app.core.security import (
    hash_password,
    verify_password,
    create_access_token,
    generate_refresh_token,
    hash_token
)
from app.api.deps import get_current_user
from app.repositories.user_repo import UserRepository
from app.repositories.token_repo import TokenRepository
from app.repositories.audit_repo import AuditRepository
from app.schemas.user import UserCreate, UserInDB
from app.schemas.audit import AuditAction

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/register", status_code=status.HTTP_201_CREATED)
async def register(
    user_data: UserCreate,
    request: Request,
    db: asyncpg.Connection = Depends(get_db_connection)
):
    user_repo = UserRepository(db)
    audit_repo = AuditRepository(db)

    if await user_repo.exists_by_username(user_data.username):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f'Пользователь с никнеймом "{user_data.username}" уже существует'
        )

    new_user = UserInDB(
        username=user_data.username,
        password=hash_password(user_data.password),
        bio=user_data.bio
    )
    user_id = await user_repo.create_user(new_user)

    await audit_repo.log_action(
        user_id=user_id,
        username=new_user.username,
        action=AuditAction.USER_REGISTERED,
        target_type="user",
        target_id=user_id,
        target_name=new_user.username,
        ip_address=request.client.host,
        user_agent=request.headers.get("user-agent")
    )

    return {"status": "success"}


@router.post("/login")
async def login(
    response: Response,
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: asyncpg.Connection = Depends(get_db_connection)
):
    user_repo = UserRepository(db)
    token_repo = TokenRepository(db)
    audit_repo = AuditRepository(db)

    ip_address = request.client.host
    user_agent = request.headers.get("user-agent")

    user = await user_repo.get_by_username(form_data.username)
    if not user or not verify_password(form_data.password, user["password"]):
        await audit_repo.log_action(
            user_id=user["id"] if user else None,
            username=form_data.username,
            action=AuditAction.LOGIN_FAILED,
            target_type="user",
            ip_address=ip_address,
            user_agent=user_agent
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Неверный логин или пароль",
            headers={"WWW-Authenticate": "Bearer"}
        )

    access_token = create_access_token({"sub": user["username"]})
    raw_refresh_token, token_hash, expires_at = generate_refresh_token()

    await token_repo.create_refresh_token(token_hash, user["id"], expires_at)

    response.set_cookie(
        key="refresh_token",
        value=raw_refresh_token,
        httponly=True,
        secure=settings.IS_PRODUCTION,
        samesite="lax",
        max_age=settings.REFRESH_COOKIE_MAX_AGE,
        path="/"
    )

    await audit_repo.log_action(
        user_id=user["id"],
        username=user["username"],
        action=AuditAction.LOGIN_SUCCESS,
        target_type="user",
        target_id=user["id"],
        target_name=user["username"],
        ip_address=ip_address,
        user_agent=user_agent
    )

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "message": "Вход выполнен успешно"
    }


@router.post("/logout")
async def logout(
    request: Request,
    response: Response,
    refresh_token: str | None = Cookie(default=None),
    db: asyncpg.Connection = Depends(get_db_connection)
):
    if not refresh_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="No refresh token")

    token_repo = TokenRepository(db)
    user_repo = UserRepository(db)
    audit_repo = AuditRepository(db)

    token_hash = hash_token(refresh_token)
    token_record = await token_repo.get_refresh_token(token_hash)
    
    if not token_record:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Токен не найден")

    user_id = token_record["user_id"]
    user = await user_repo.get_by_id(user_id)
    username = user["username"] if user else None

    # Отзываем токен
    await token_repo.revoke_single_refresh(token_hash)
    response.delete_cookie("refresh_token")

    await audit_repo.log_action(
        user_id=user_id,
        username=username,
        action=AuditAction.LOGOUT,
        target_id=user_id,
        target_type="user",
        target_name=username,
        ip_address=request.client.host,
        user_agent=request.headers.get("user-agent")
    )

    return {"message": "Logged out successfully"}


@router.post("/logout-all")
async def logout_all_sessions(
    response: Response,
    current_user: dict = Depends(get_current_user),
    db: asyncpg.Connection = Depends(get_db_connection)
):
    token_repo = TokenRepository(db)
    revoked = await token_repo.revoke_all_user_tokens(current_user["id"])
    
    if not revoked:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Активные сессии не найдены")

    response.delete_cookie("refresh_token")
    return {"message": "All sessions are closed"}


@router.post("/refresh")
async def refresh_tokens(
    response: Response,
    refresh_token: str | None = Cookie(default=None),
    db: asyncpg.Connection = Depends(get_db_connection)
):
    if not refresh_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="No refresh token")

    token_repo = TokenRepository(db)
    user_repo = UserRepository(db)

    token_hash = hash_token(refresh_token)
    row = await token_repo.get_refresh_token(token_hash)

    if not row:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")

    if row["is_revoked"]:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token revoked")

    user = await user_repo.get_by_id(row["user_id"])
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    await token_repo.revoke_single_refresh(token_hash)

    new_access_token = create_access_token({"sub": user["username"]})
    raw_new_refresh, new_hash, expires_at = generate_refresh_token()
    await token_repo.create_refresh_token(new_hash, user["id"], expires_at)

    response.set_cookie(
        key="refresh_token",
        value=raw_new_refresh,
        httponly=True,
        secure=settings.IS_PRODUCTION,
        samesite="lax",
        max_age=settings.REFRESH_COOKIE_MAX_AGE,
        path="/"
    )

    return {
        "access_token": new_access_token,
        "token_type": "bearer"
    }