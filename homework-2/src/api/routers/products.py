from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional

from src.api.models import (
    ProductCreate, ProductUpdate, ProductResponse, ProductPageResponse,
    ProductStatus
)
from src.db.database import get_db
from src.services.product_service import ProductService, get_current_user, CurrentUser

router = APIRouter(
    prefix="/products",
    tags=["Products"]
)


@router.post(
    "", 
    response_model=ProductResponse, 
    status_code=status.HTTP_201_CREATED,
    summary="Создать товар (Только SELLER или ADMIN)"
)
async def create_product(
    product_data: ProductCreate,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user)
):
    if current_user.role not in ["SELLER", "ADMIN"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error_code": "ACCESS_DENIED", "message": "Только продавец или администратор может создавать товары"}
        )

    service = ProductService(db)
    return await service.create_product(product_data, current_user)


@router.get(
    "",
    response_model=ProductPageResponse,
    summary="Получить список товаров с пагинацией и фильтрацией"
)
async def get_products(
    page: int = Query(0, ge=0),
    size: int = Query(20, ge=1, le=100),
    status: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    min_price: Optional[float] = Query(None, ge=0),
    max_price: Optional[float] = Query(None, ge=0),
    db: AsyncSession = Depends(get_db)
):
    # Валидация статуса (если передан)
    if status is not None and status not in ["ACTIVE", "INACTIVE", "ARCHIVED"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"error_code": "VALIDATION_ERROR", "message": "Недопустимое значение статуса"}
        )
    
    service = ProductService(db)
    return await service.get_products(
        page=page,
        size=size,
        status_filter=status,
        category=category,
        min_price=min_price,
        max_price=max_price
    )


@router.get(
    "/{product_id}",
    response_model=ProductResponse,
    summary="Получить товар по ID"
)
async def get_product(
    product_id: UUID,
    db: AsyncSession = Depends(get_db)
):
    service = ProductService(db)
    return await service.get_product_by_id(product_id)


@router.put(
    "/{product_id}",
    response_model=ProductResponse,
    summary="Обновить товар (Только владелец или ADMIN)"
)
async def update_product(
    product_id: UUID,
    product_data: ProductUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user)
):
    service = ProductService(db)
    return await service.update_product(product_id, product_data, current_user)


@router.delete(
    "/{product_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
    summary="Мягкое удаление товара (перевод в ARCHIVED)"
)
async def delete_product(
    product_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user)
):
    service = ProductService(db)
    await service.delete_product(product_id, current_user)