from uuid import UUID
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from fastapi import HTTPException, status

from src.api.models import PromoCodeCreate, PromoCodeResponse
from src.models.orm_models import PromoCode


def promo_to_dict(promo: PromoCode) -> dict:
    return {
        "id": str(promo.id),
        "code": promo.code,
        "discount_type": promo.discount_type.value if hasattr(promo.discount_type, 'value') else promo.discount_type,
        "discount_value": float(promo.discount_value) if isinstance(promo.discount_value, Decimal) else promo.discount_value,
        "min_order_amount": float(promo.min_order_amount) if isinstance(promo.min_order_amount, Decimal) else promo.min_order_amount,
        "max_uses": promo.max_uses,
        "current_uses": promo.current_uses,
        "valid_from": promo.valid_from.isoformat() if hasattr(promo.valid_from, 'isoformat') else promo.valid_from,
        "valid_until": promo.valid_until.isoformat() if hasattr(promo.valid_until, 'isoformat') else promo.valid_until,
        "active": promo.active,
    }


class PromoService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_promo_code(self, data: PromoCodeCreate) -> PromoCodeResponse:
        """Создание промокода"""
        # Проверка уникальности кода
        result = await self.db.execute(
            select(PromoCode).where(PromoCode.code == data.code)
        )
        if result.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"error_code": "PROMO_CODE_ALREADY_EXISTS", "message": "Промокод с таким кодом уже существует"}
            )
        
        # Валидация дат
        valid_from = data.valid_from
        valid_until = data.valid_until
        if valid_from >= valid_until:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"error_code": "VALIDATION_ERROR", "message": "Дата окончания должна быть позже даты начала"}
            )
        
        promo = PromoCode(
            code=data.code,
            discount_type=data.discount_type.value if hasattr(data.discount_type, 'value') else data.discount_type,
            discount_value=data.discount_value,
            min_order_amount=data.min_order_amount or 0,
            max_uses=data.max_uses,
            current_uses=0,
            valid_from=valid_from,
            valid_until=valid_until,
            active=True
        )
        
        self.db.add(promo)
        await self.db.commit()
        await self.db.refresh(promo)
        
        return PromoCodeResponse(**promo_to_dict(promo))

    async def get_promo_by_code(self, code: str) -> PromoCode:
        """Получение промокода по коду с валидацией"""
        result = await self.db.execute(
            select(PromoCode).where(PromoCode.code == code)
        )
        promo = result.scalar_one_or_none()
        
        if not promo:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={"error_code": "PROMO_CODE_INVALID", "message": "Промокод не найден"}
            )
        
        now = datetime.now(timezone.utc)
        
        if not promo.active:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={"error_code": "PROMO_CODE_INVALID", "message": "Промокод неактивен"}
            )
        
        if promo.current_uses >= promo.max_uses:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={"error_code": "PROMO_CODE_INVALID", "message": "Промокод исчерпан"}
            )
        
        if now < promo.valid_from or now > promo.valid_until:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={"error_code": "PROMO_CODE_INVALID", "message": "Промокод истёк или ещё не активен"}
            )
        
        return promo

    async def apply_promo_code(self, promo: PromoCode, total_amount: float) -> float:
        """
        Применяет промокод и возвращает размер скидки.
        Также увеличивает current_uses.
        """
        min_amount = float(promo.min_order_amount) if isinstance(promo.min_order_amount, Decimal) else promo.min_order_amount
        
        if total_amount < min_amount:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail={"error_code": "PROMO_CODE_MIN_AMOUNT", "message": f"Сумма заказа ниже минимальной ({min_amount}) для промокода"}
            )
        
        discount_type = promo.discount_type.value if hasattr(promo.discount_type, 'value') else promo.discount_type
        discount_value = float(promo.discount_value) if isinstance(promo.discount_value, Decimal) else promo.discount_value
        
        if discount_type == "PERCENTAGE":
            discount = total_amount * discount_value / 100
            # Ограничение 70% по заданию
            if discount > total_amount * 0.7:
                discount = total_amount * 0.7
        else:  # FIXED_AMOUNT
            discount = discount_value
            if discount > total_amount:
                discount = total_amount
        
        # Увеличиваем счётчик использований
        promo.current_uses += 1
        await self.db.flush()  # flush, не commit
        
        return discount