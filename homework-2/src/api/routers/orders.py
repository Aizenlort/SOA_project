from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.models import (
    OrderCreate, OrderUpdate, OrderResponse, OrderPageResponse
)
from src.db.database import get_db
from src.services.order_service import OrderService
from src.services.product_service import get_current_user, CurrentUser

router = APIRouter(
    prefix="/orders",
    tags=["Orders"]
)


@router.post(
    "",
    response_model=OrderResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Создать заказ"
)
async def create_order(
    data: OrderCreate,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user)
):
    if current_user.role not in ["USER", "ADMIN"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error_code": "ACCESS_DENIED", "message": "Только пользователь или администратор может создавать заказы"}
        )
    
    service = OrderService(db)
    return await service.create_order(data, current_user)


@router.get(
    "",
    response_model=OrderPageResponse,
    summary="Получить мои заказы"
)
async def get_my_orders(
    page: int = Query(0, ge=0),
    size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user)
):
    service = OrderService(db)
    return await service.get_my_orders(current_user, page, size)


@router.get(
    "/{order_id}",
    response_model=OrderResponse,
    summary="Получить заказ по ID"
)
async def get_order(
    order_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user)
):
    service = OrderService(db)
    return await service.get_order_by_id(order_id, current_user)


@router.put(
    "/{order_id}",
    response_model=OrderResponse,
    summary="Обновить позиции заказа"
)
async def update_order(
    order_id: UUID,
    data: OrderUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user)
):
    service = OrderService(db)
    return await service.update_order(order_id, data, current_user)


@router.post(
    "/{order_id}/cancel",
    response_model=OrderResponse,
    summary="Отменить заказ"
)
async def cancel_order(
    order_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user)
):
    service = OrderService(db)
    return await service.cancel_order(order_id, current_user)