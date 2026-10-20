from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from fastapi import HTTPException, status

from src.api.models import UserRegister, UserLogin, UserResponse, TokenResponse
from src.models.orm_models import User
from src.core.security import (
    verify_password,
    get_password_hash,
    create_access_token,
    create_refresh_token,
    decode_token
)
from src.core.config import settings

class AuthService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def register(self, user_data: UserRegister) -> UserResponse:
        """Регистрация нового пользователя"""
        # Проверяем, не занят ли email
        result = await self.db.execute(
            select(User).where(User.email == user_data.email)
        )
        existing_user = result.scalar_one_or_none()

        if existing_user:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "error_code": "EMAIL_ALREADY_EXISTS",
                    "message": "Пользователь с таким email уже зарегистрирован"
                }
            )

        # Создаем пользователя
        db_user = User(
            email=user_data.email,
            password_hash=get_password_hash(user_data.password),
            role=user_data.role.value if hasattr(user_data.role, 'value') else user_data.role
        )

        self.db.add(db_user)
        await self.db.commit()
        await self.db.refresh(db_user)

        return UserResponse(
            id=db_user.id,
            email=db_user.email,
            role=db_user.role
        )

    async def login(self, login_data: UserLogin) -> TokenResponse:
        """Вход пользователя и выдача токенов"""
        # Ищем пользователя по email
        result = await self.db.execute(
            select(User).where(User.email == login_data.email)
        )
        user = result.scalar_one_or_none()

        # Проверяем пароль
        if not user or not verify_password(login_data.password, user.password_hash):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={
                    "error_code": "INVALID_CREDENTIALS",
                    "message": "Неверный email или пароль"
                }
            )

        # Создаем токены
        token_data = {
            "sub": str(user.id),
            "role": user.role,
            "email": user.email
        }

        access_token = create_access_token(token_data)
        refresh_token = create_refresh_token(token_data)

        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="bearer"
        )

    async def refresh_access_token(self, refresh_token: str) -> TokenResponse:
        """Обновление access token по refresh token"""
        # Декодируем refresh token
        payload = decode_token(refresh_token, token_type="refresh")

        user_id = payload.get("sub")
        role = payload.get("role")
        email = payload.get("email")

        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={
                    "error_code": "REFRESH_TOKEN_INVALID",
                    "message": "Невалидный refresh token"
                }
            )

        # Проверяем, существует ли пользователь
        result = await self.db.execute(
            select(User).where(User.id == UUID(user_id))
        )
        user = result.scalar_one_or_none()

        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail={
                    "error_code": "REFRESH_TOKEN_INVALID",
                    "message": "Пользователь не найден"
                }
            )

        # Создаем новые токены
        token_data = {
            "sub": str(user.id),
            "role": user.role,
            "email": user.email
        }

        new_access_token = create_access_token(token_data)
        new_refresh_token = create_refresh_token(token_data)

        return TokenResponse(
            access_token=new_access_token,
            refresh_token=new_refresh_token,
            token_type="bearer"
        )