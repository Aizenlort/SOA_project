from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.models import PromoCodeCreate, PromoCodeResponse
from src.db.database import get_db
from src.services.promo_service import PromoService
from src.services.product_service import get_current_user, CurrentUser

router = APIRouter(
    prefix="/promo-codes",
    tags=["PromoCodes"]
)


@router.post(
    "",
    response_model=PromoCodeResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Создать промокод (SELLER или ADMIN)"
)
async def create_promo_code(
    data: PromoCodeCreate,
    db: AsyncSession = Depends(get_db),
    current_user: CurrentUser = Depends(get_current_user)
):
    if current_user.role not in ["SELLER", "ADMIN"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"error_code": "ACCESS_DENIED", "message": "Только продавец или администратор может создавать промокоды"}
        )
    
    service = PromoService(db)
    return await service.create_promo_code(data)