from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.deps import get_db, get_current_user
from app.models.user import User
from app.db.session import SessionLocal
from app.schemas.user import UserResponse, UserBrief
from app.services.subscription import SubscriptionService


router = APIRouter(prefix="/subscriptions", tags=["subscriptions"])

@router.post("/toggle/{target_id}")
async def toggle_subscription(
    target_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    result = await SubscriptionService.toggle_subscription(
        db=db, user_id=current_user.id, target_id=target_id
    )
    return result

@router.get("/{user_id}/followers", response_model=list[UserBrief])
async def get_user_followers(
        user_id: int,
        db: AsyncSession = Depends(get_db),
):
    """Отримання підписників конкретного користувача"""
    return await SubscriptionService.get_followers(db, user_id)

@router.get("/{user_id}/following", response_model=list[UserBrief])
async def get_user_following(
    user_id: int,
    db: AsyncSession = Depends(get_db)
):
    """Отримати списки тих, на кого підписаний конкретний користувач"""
    return await SubscriptionService.get_following(db, user_id)