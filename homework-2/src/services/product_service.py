from uuid import UUID
from decimal import Decimal
from datetime import datetime
from typing import Optional, List, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, update
from sqlalchemy.sql import Select
from fastapi import Depends, HTTPException, status

from src.api.models import (
    ProductCreate, ProductUpdate, ProductResponse, ProductPageResponse,
    ProductStatus
)
from src.models.orm_models import Product, User
from src.db.database import get_db
from src.core.security import decode_token


class CurrentUser:
    """Модель текущего авторизованного пользователя"""
    def __init__(self, user_id: UUID, email: str, role: str):
        self.id = user_id
        self.email = email
        self.role = role


async def get_current_user(
    authorization: str,
    db: AsyncSession = Depends(get_db)
) -> CurrentUser:
    """Извлекает текущего пользователя из JWT токена"""
    if not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error_code": "TOKEN_INVALID", "message": "Неверный формат заголовка авторизации"}
        )
    
    token = authorization.split(" ")[1]
    payload = decode_token(token, token_type="access")
    
    user_id = payload.get("sub")
    role = payload.get("role")
    email = payload.get("email")
    
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error_code": "TOKEN_INVALID", "message": "Токен не содержит идентификатор пользователя"}
        )
    
    result = await db.execute(select(User).where(User.id == UUID(user_id)))
    user = result.scalar_one_or_none()
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error_code": "TOKEN_INVALID", "message": "Пользователь не найден"}
        )
    
    return CurrentUser(user_id=user.id, email=user.email, role=user.role)


def product_to_dict(product: Product) -> dict:
    """Вспомогательная функция конвертации ORM объекта в словарь для Pydantic"""
    return {
        "id": str(product.id),
        "name": product.name,
        "description": product.description,
        "price": float(product.price) if isinstance(product.price, Decimal) else product.price,
        "stock": product.stock,
        "category": product.category,
        "status": product.status.value if hasattr(product.status, 'value') else product.status,
        "seller_id": str(product.seller_id),
        "created_at": product.created_at.isoformat() if isinstance(product.created_at, datetime) else product.created_at,
        "updated_at": product.updated_at.isoformat() if isinstance(product.updated_at, datetime) else product.updated_at,
    }


class ProductService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_product_by_id(self, product_id: UUID) -> ProductResponse:
        """Получение товара по ID"""
        result = await self.db.execute(
            select(Product).where(Product.id == product_id)
        )
        product = result.scalar_one_or_none()
        
        if not product:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error_code": "PRODUCT_NOT_FOUND", "message": "Товар не найден по ID"}
            )
        
        return ProductResponse(**product_to_dict(product))

    async def get_products(
        self,
        page: int = 0,
        size: int = 20,
        status_filter: Optional[str] = None,
        category: Optional[str] = None,
        min_price: Optional[float] = None,
        max_price: Optional[float] = None
    ) -> ProductPageResponse:
        """Получение списка товаров с пагинацией и фильтрацией"""
        # Базовый запрос
        query = select(Product)
        count_query = select(func.count(Product.id))
        
        # Применяем фильтры
        filters = []
        if status_filter:
            filters.append(Product.status == status_filter)
        if category:
            filters.append(Product.category == category)
        if min_price is not None:
            filters.append(Product.price >= min_price)
        if max_price is not None:
            filters.append(Product.price <= max_price)
        
        if filters:
            query = query.where(and_(*filters))
            count_query = count_query.where(and_(*filters))
        
        # Получаем общее количество
        total_result = await self.db.execute(count_query)
        total_elements = total_result.scalar() or 0
        
        # Применяем пагинацию
        query = query.offset(page * size).limit(size).order_by(Product.created_at.desc())
        result = await self.db.execute(query)
        products = result.scalars().all()
        
        # Формируем ответ
        content = [ProductResponse(**product_to_dict(p)) for p in products]
        total_pages = (total_elements + size - 1) // size if size > 0 else 0
        
        return ProductPageResponse(
            content=content,
            totalElements=total_elements,
            pageNumber=page,
            pageSize=size,
            totalPages=total_pages
        )

    async def create_product(self, product_data: ProductCreate, seller: CurrentUser) -> ProductResponse:
        """Создание товара"""
        db_product = Product(
            name=product_data.name,
            description=product_data.description,
            price=product_data.price,
            stock=product_data.stock,
            category=product_data.category,
            seller_id=seller.id,
            status="ACTIVE"
        )

        self.db.add(db_product)
        await self.db.commit()
        await self.db.refresh(db_product)

        return ProductResponse(**product_to_dict(db_product))

    async def update_product(
        self, product_id: UUID, product_data: ProductUpdate, current_user: CurrentUser
    ) -> ProductResponse:
        """Обновление товара (только владелец или ADMIN)"""
        # Получаем товар
        result = await self.db.execute(
            select(Product).where(Product.id == product_id)
        )
        product = result.scalar_one_or_none()
        
        if not product:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error_code": "PRODUCT_NOT_FOUND", "message": "Товар не найден по ID"}
            )
        
        # Проверка прав: только владелец или ADMIN может обновлять
        if current_user.role not in ["ADMIN"] and product.seller_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"error_code": "ACCESS_DENIED", "message": "Вы не являетесь владельцем этого товара"}
            )
        
        # Обновляем только переданные поля
        if product_data.name is not None:
            product.name = product_data.name
        if product_data.description is not None:
            product.description = product_data.description
        if product_data.price is not None:
            product.price = product_data.price
        if product_data.stock is not None:
            product.stock = product_data.stock
        if product_data.category is not None:
            product.category = product_data.category
        if product_data.status is not None:
            status_value = product_data.status.value if hasattr(product_data.status, 'value') else product_data.status
            product.status = status_value
        
        await self.db.commit()
        await self.db.refresh(product)
        
        return ProductResponse(**product_to_dict(product))

    async def delete_product(self, product_id: UUID, current_user: CurrentUser) -> None:
        """Мягкое удаление товара (перевод в статус ARCHIVED)"""
        # Получаем товар
        result = await self.db.execute(
            select(Product).where(Product.id == product_id)
        )
        product = result.scalar_one_or_none()
        
        if not product:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error_code": "PRODUCT_NOT_FOUND", "message": "Товар не найден по ID"}
            )
        
        # Проверка прав
        if current_user.role not in ["ADMIN"] and product.seller_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"error_code": "ACCESS_DENIED", "message": "Вы не являетесь владельцем этого товара"}
            )
        
        # Мягкое удаление
        product.status = "ARCHIVED"
        await self.db.commit()