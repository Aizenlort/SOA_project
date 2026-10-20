from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.models import UserRegister, UserLogin, UserResponse, TokenResponse, RefreshRequest
from src.db.database import get_db
from src.services.auth_service import AuthService

router = APIRouter(
    prefix="/auth",
    tags=["Auth"]
)

@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Регистрация пользователя"
)
async def register(
    user_data: UserRegister,
    db: AsyncSession = Depends(get_db)
):
    service = AuthService(db)
    return await service.register(user_data)

@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Вход в систему"
)
async def login(
    login_data: UserLogin,
    db: AsyncSession = Depends(get_db)
):
    service = AuthService(db)
    return await service.login(login_data)

@router.post(
    "/refresh",
    response_model=TokenResponse,
    summary="Обновление access token"
)
async def refresh_token(
    refresh_data: RefreshRequest,
    db: AsyncSession = Depends(get_db)
):
    service = AuthService(db)
    return await service.refresh_access_token(refresh_data.refresh_token)