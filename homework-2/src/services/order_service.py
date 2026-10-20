from uuid import UUID
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, update, text
from fastapi import HTTPException, status

from src.api.models import (
    OrderCreate, OrderUpdate, OrderResponse, OrderPageResponse,
    OrderItemResponse, OrderStatus
)
from src.models.orm_models import Order, OrderItem, Product, User, UserOperation, PromoCode
from src.services.product_service import CurrentUser, product_to_dict
from src.services.promo_service import PromoService


def order_to_dict(order: Order, items: List[OrderItem] = None) -> dict:
    """Конвертация заказа в словарь"""
    result = {
        "id": str(order.id),
        "user_id": str(order.user_id),
        "status": order.status.value if hasattr(order.status, 'value') else order.status,
        "total_amount": float(order.total_amount) if isinstance(order.total_amount, Decimal) else order.total_amount,
        "discount_amount": float(order.discount_amount) if isinstance(order.discount_amount, Decimal) else order.discount_amount,
        "promo_code": order.promo_code_id,  # код промокода подставим отдельно
        "created_at": order.created_at.isoformat() if hasattr(order.created_at, 'isoformat') else order.created_at,
        "updated_at": order.updated_at.isoformat() if hasattr(order.updated_at, 'isoformat') else order.updated_at,
    }
    
    if items is not None:
        result["items"] = [
            {
                "product_id": str(item.product_id),
                "product_name": item.product_name if hasattr(item, 'product_name') else None,
                "quantity": item.quantity,
                "price_at_order": float(item.price_at_order) if isinstance(item.price_at_order, Decimal) else item.price_at_order,
            }
            for item in items
        ]
    else:
        result["items"] = []
    
    return result


class OrderService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.promo_service = PromoService(db)

    async def _check_rate_limit(self, user_id: UUID, operation_type: str, limit_minutes: int = 1):
        """Проверка лимита частоты операций (п.7 задания)"""
        cutoff_time = datetime.now(timezone.utc) - timedelta(minutes=limit_minutes)
        
        result = await self.db.execute(
            select(func.count(UserOperation.id)).where(
                and_(
                    UserOperation.user_id == user_id,
                    UserOperation.operation_type == operation_type,
                    UserOperation.created_at >= cutoff_time
                )
            )
        )
        count = result.scalar() or 0
        
        # Лимит: не более 1 операции в минуту (настраиваемо)
        if count >= 1:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail={"error_code": "ORDER_LIMIT_EXCEEDED", "message": f"Превышен лимит частоты {operation_type}"}
            )

    async def _check_active_orders(self, user_id: UUID):
        """Проверка наличия активных заказов"""
        result = await self.db.execute(
            select(func.count(Order.id)).where(
                and_(
                    Order.user_id == user_id,
                    Order.status.in_(["CREATED", "PAYMENT_PENDING"])
                )
            )
        )
        count = result.scalar() or 0
        
        if count > 0:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"error_code": "ORDER_HAS_ACTIVE", "message": "У пользователя уже есть активный заказ"}
            )

    async def create_order(self, data: OrderCreate, current_user: CurrentUser) -> OrderResponse:
        """
        Создание заказа с полной транзакционной защитой.
        """
        # === ЭТАП 1: Проверки БЕЗ транзакции ===
        
        # 1.1. Проверка лимита частоты
        await self._check_rate_limit(current_user.id, "CREATE_ORDER")
        
        # 1.2. Проверка активных заказов
        await self._check_active_orders(current_user.id)
        
        # 1.3. Валидация товаров и расчёт суммы
        items_data = []
        total_amount = 0.0
        products_to_lock = []
        
        for item in data.items:
            # Получаем товар с блокировкой FOR UPDATE (защита от race condition)
            result = await self.db.execute(
                select(Product).where(Product.id == item.product_id).with_for_update()
            )
            product = result.scalar_one_or_none()
            
            if not product:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail={"error_code": "PRODUCT_NOT_FOUND", "message": f"Товар {item.product_id} не найден"}
                )
            
            product_status = product.status.value if hasattr(product.status, 'value') else product.status
            if product_status != "ACTIVE":
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail={"error_code": "PRODUCT_INACTIVE", "message": f"Товар {product.name} неактивен"}
                )
            
            if product.stock < item.quantity:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail={
                        "error_code": "INSUFFICIENT_STOCK",
                        "message": f"Недостаточно товара {product.name} на складе",
                        "details": {"available": product.stock, "requested": item.quantity}
                    }
                )
            
            price = float(product.price) if isinstance(product.price, Decimal) else product.price
            items_data.append({
                "product": product,
                "quantity": item.quantity,
                "price": price
            })
            total_amount += price * item.quantity
        
        # === ЭТАП 2: Транзакция ===
        try:
            # 2.1. Применение промокода (если есть)
            discount_amount = 0.0
            promo_code_id = None
            
            if data.promo_code:
                promo = await self.promo_service.get_promo_by_code(data.promo_code)
                discount_amount = await self.promo_service.apply_promo_code(promo, total_amount)
                promo_code_id = promo.id
                total_amount -= discount_amount
            
            # 2.2. Создание заказа
            order = Order(
                user_id=current_user.id,
                status="CREATED",
                promo_code_id=promo_code_id,
                total_amount=total_amount,
                discount_amount=discount_amount
            )
            self.db.add(order)
            await self.db.flush()  # Получаем order.id
            
            # 2.3. Создание позиций заказа и резервирование остатков
            order_items = []
            for item_data in items_data:
                product = item_data["product"]
                quantity = item_data["quantity"]
                price = item_data["price"]
                
                # Резервируем остатки (уменьшаем stock)
                product.stock -= quantity
                
                order_item = OrderItem(
                    order_id=order.id,
                    product_id=product.id,
                    quantity=quantity,
                    price_at_order=price
                )
                self.db.add(order_item)
                order_items.append(order_item)
            
            # 2.4. Фиксация операции для rate limiting
            operation = UserOperation(
                user_id=current_user.id,
                operation_type="CREATE_ORDER"
            )
            self.db.add(operation)
            
            # 2.5. Коммит транзакции
            await self.db.commit()
            
            # 2.6. Возвращаем результат
            # Перечитываем заказ с позициями
            await self.db.refresh(order)
            
            items_response = []
            for oi in order_items:
                # Получаем имя товара
                prod_result = await self.db.execute(
                    select(Product).where(Product.id == oi.product_id)
                )
                prod = prod_result.scalar_one_or_none()
                items_response.append(OrderItemResponse(
                    product_id=oi.product_id,
                    product_name=prod.name if prod else None,
                    quantity=oi.quantity,
                    price_at_order=float(oi.price_at_order) if isinstance(oi.price_at_order, Decimal) else oi.price_at_order
                ))
            
            return OrderResponse(
                id=order.id,
                user_id=order.user_id,
                status=order.status,
                total_amount=float(order.total_amount) if isinstance(order.total_amount, Decimal) else order.total_amount,
                discount_amount=float(order.discount_amount) if isinstance(order.discount_amount, Decimal) else order.discount_amount,
                promo_code=data.promo_code,
                items=items_response,
                created_at=order.created_at,
                updated_at=order.updated_at
            )
            
        except HTTPException:
            await self.db.rollback()
            raise
        except Exception as e:
            await self.db.rollback()
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail={"error_code": "INTERNAL_ERROR", "message": str(e)}
            )

    async def get_order_by_id(self, order_id: UUID, current_user: CurrentUser) -> OrderResponse:
        """Получение заказа по ID"""
        result = await self.db.execute(
            select(Order).where(Order.id == order_id)
        )
        order = result.scalar_one_or_none()
        
        if not order:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error_code": "ORDER_NOT_FOUND", "message": "Заказ не найден"}
            )
        
        # Проверка владения (USER видит только свои, ADMIN - все)
        if current_user.role != "ADMIN" and order.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"error_code": "ORDER_OWNERSHIP_VIOLATION", "message": "Заказ принадлежит другому пользователю"}
            )
        
        # Получаем позиции
        items_result = await self.db.execute(
            select(OrderItem).where(OrderItem.order_id == order.id)
        )
        items = items_result.scalars().all()
        
        items_response = []
        for item in items:
            prod_result = await self.db.execute(
                select(Product).where(Product.id == item.product_id)
            )
            prod = prod_result.scalar_one_or_none()
            items_response.append(OrderItemResponse(
                product_id=item.product_id,
                product_name=prod.name if prod else None,
                quantity=item.quantity,
                price_at_order=float(item.price_at_order) if isinstance(item.price_at_order, Decimal) else item.price_at_order
            ))
        
        return OrderResponse(
            id=order.id,
            user_id=order.user_id,
            status=order.status,
            total_amount=float(order.total_amount) if isinstance(order.total_amount, Decimal) else order.total_amount,
            discount_amount=float(order.discount_amount) if isinstance(order.discount_amount, Decimal) else order.discount_amount,
            promo_code=None,
            items=items_response,
            created_at=order.created_at,
            updated_at=order.updated_at
        )

    async def get_my_orders(self, current_user: CurrentUser, page: int = 0, size: int = 20) -> OrderPageResponse:
        """Получение списка заказов (USER - свои, ADMIN - все)"""
        if current_user.role == "ADMIN":
            count_result = await self.db.execute(select(func.count(Order.id)))
            query = select(Order).order_by(Order.created_at.desc())
        else:
            count_result = await self.db.execute(
                select(func.count(Order.id)).where(Order.user_id == current_user.id)
            )
            query = select(Order).where(Order.user_id == current_user.id).order_by(Order.created_at.desc())
        
        total = count_result.scalar() or 0
        query = query.offset(page * size).limit(size)
        result = await self.db.execute(query)
        orders = result.scalars().all()
        
        content = []
        for order in orders:
            items_result = await self.db.execute(
                select(OrderItem).where(OrderItem.order_id == order.id)
            )
            items = items_result.scalars().all()
            items_response = []
            for item in items:
                items_response.append(OrderItemResponse(
                    product_id=item.product_id,
                    product_name=None,
                    quantity=item.quantity,
                    price_at_order=float(item.price_at_order) if isinstance(item.price_at_order, Decimal) else item.price_at_order
                ))
            
            content.append(OrderResponse(
                id=order.id,
                user_id=order.user_id,
                status=order.status,
                total_amount=float(order.total_amount) if isinstance(order.total_amount, Decimal) else order.total_amount,
                discount_amount=float(order.discount_amount) if isinstance(order.discount_amount, Decimal) else order.discount_amount,
                promo_code=None,
                items=items_response,
                created_at=order.created_at,
                updated_at=order.updated_at
            ))
        
        total_pages = (total + size - 1) // size if size > 0 else 0
        
        return OrderPageResponse(
            content=content,
            totalElements=total,
            pageNumber=page,
            pageSize=size,
            totalPages=total_pages
        )

    async def update_order(self, order_id: UUID, data: OrderUpdate, current_user: CurrentUser) -> OrderResponse:
        """Обновление позиций заказа (только в статусе CREATED)"""
        # Получаем заказ с блокировкой
        result = await self.db.execute(
            select(Order).where(Order.id == order_id).with_for_update()
        )
        order = result.scalar_one_or_none()
        
        if not order:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error_code": "ORDER_NOT_FOUND", "message": "Заказ не найден"}
            )
        
        # Проверка владения
        if current_user.role != "ADMIN" and order.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"error_code": "ORDER_OWNERSHIP_VIOLATION", "message": "Заказ принадлежит другому пользователю"}
            )
        
        # Проверка статуса
        order_status = order.status.value if hasattr(order.status, 'value') else order.status
        if order_status != "CREATED":
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"error_code": "INVALID_STATE_TRANSITION", "message": "Заказ можно изменять только в статусе CREATED"}
            )
        
        # Проверка лимита
        await self._check_rate_limit(current_user.id, "UPDATE_ORDER")
        
        try:
            # Возвращаем старые остатки
            old_items_result = await self.db.execute(
                select(OrderItem).where(OrderItem.order_id == order.id)
            )
            old_items = old_items_result.scalars().all()
            
            for old_item in old_items:
                await self.db.execute(
                    update(Product).where(Product.id == old_item.product_id).values(
                        stock=Product.stock + old_item.quantity
                    )
                )
            
            # Удаляем старые позиции
            for old_item in old_items:
                await self.db.delete(old_item)
            
            # Валидация новых товаров
            new_total = 0.0
            new_items_data = []
            
            for item in data.items:
                prod_result = await self.db.execute(
                    select(Product).where(Product.id == item.product_id).with_for_update()
                )
                product = prod_result.scalar_one_or_none()
                
                if not product:
                    raise HTTPException(
                        status_code=status.HTTP_404_NOT_FOUND,
                        detail={"error_code": "PRODUCT_NOT_FOUND", "message": f"Товар {item.product_id} не найден"}
                    )
                
                product_status = product.status.value if hasattr(product.status, 'value') else product.status
                if product_status != "ACTIVE":
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail={"error_code": "PRODUCT_INACTIVE", "message": f"Товар {product.name} неактивен"}
                    )
                
                if product.stock < item.quantity:
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail={"error_code": "INSUFFICIENT_STOCK", "message": f"Недостаточно товара {product.name}"}
                    )
                
                price = float(product.price) if isinstance(product.price, Decimal) else product.price
                new_items_data.append({"product": product, "quantity": item.quantity, "price": price})
                new_total += price * item.quantity
            
            # Применяем промокод (если есть)
            discount = 0.0
            if data.promo_code:
                promo = await self.promo_service.get_promo_by_code(data.promo_code)
                discount = await self.promo_service.apply_promo_code(promo, new_total)
                order.promo_code_id = promo.id
            
            order.total_amount = new_total - discount
            order.discount_amount = discount
            
            # Создаём новые позиции
            for item_data in new_items_data:
                product = item_data["product"]
                product.stock -= item_data["quantity"]
                
                new_item = OrderItem(
                    order_id=order.id,
                    product_id=product.id,
                    quantity=item_data["quantity"],
                    price_at_order=item_data["price"]
                )
                self.db.add(new_item)
            
            # Фиксируем операцию
            operation = UserOperation(user_id=current_user.id, operation_type="UPDATE_ORDER")
            self.db.add(operation)
            
            await self.db.commit()
            await self.db.refresh(order)
            
            return await self.get_order_by_id(order.id, current_user)
            
        except HTTPException:
            await self.db.rollback()
            raise
        except Exception as e:
            await self.db.rollback()
            raise HTTPException(status_code=500, detail=str(e))

    async def cancel_order(self, order_id: UUID, current_user: CurrentUser) -> OrderResponse:
        """Отмена заказа с возвратом остатков"""
        result = await self.db.execute(
            select(Order).where(Order.id == order_id).with_for_update()
        )
        order = result.scalar_one_or_none()
        
        if not order:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"error_code": "ORDER_NOT_FOUND", "message": "Заказ не найден"}
            )
        
        if current_user.role != "ADMIN" and order.user_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"error_code": "ORDER_OWNERSHIP_VIOLATION", "message": "Заказ принадлежит другому пользователю"}
            )
        
        order_status = order.status.value if hasattr(order.status, 'value') else order.status
        if order_status not in ["CREATED", "PAYMENT_PENDING"]:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={"error_code": "INVALID_STATE_TRANSITION", "message": "Можно отменить только заказ в статусе CREATED или PAYMENT_PENDING"}
            )
        
        try:
            # Возвращаем остатки
            items_result = await self.db.execute(
                select(OrderItem).where(OrderItem.order_id == order.id)
            )
            items = items_result.scalars().all()
            
            for item in items:
                await self.db.execute(
                    update(Product).where(Product.id == item.product_id).values(
                        stock=Product.stock + item.quantity
                    )
                )
            
            order.status = "CANCELED"
            await self.db.commit()
            await self.db.refresh(order)
            
            return await self.get_order_by_id(order.id, current_user)
            
        except HTTPException:
            await self.db.rollback()
            raise
        except Exception as e:
            await self.db.rollback()
            raise HTTPException(status_code=500, detail=str(e))