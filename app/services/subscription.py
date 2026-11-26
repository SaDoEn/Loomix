from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from fastapi import HTTPException, status
from app.models.subscriptions import Subscription
from app.models.user import User

class SubscriptionService:
    @staticmethod
    async def toggle_subscription(db: AsyncSession, user_id: int, target_id: int):
        if user_id == target_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="You cannot subscribe to yourself"
            )

        query = select(Subscription).where(
            Subscription.user_id == user_id,
            Subscription.target_user_id == target_id
        )
        result = await db.execute(query)
        existing_sub = result.scalars().first()

        if existing_sub:
            await db.delete(existing_sub)
            await db.commit()
            return {"status": "unsubscribed"}
        else:
            new_sub = Subscription(user_id=user_id, target_user_id=target_id)
            db.add(new_sub)
            await db.commit()
            return {"status": "subscribed"}

    @staticmethod
    async def get_followers(db: AsyncSession, user_id: int) -> list[User]:
        """Отримати список користувачів, які підписані на user_id"""
        stmt = (
            select(User)
            .join(Subscription, Subscription.user_id == User.id)
            .where(Subscription.target_user_id == user_id)
        )
        result = await db.execute(stmt)
        return result.scalars().all()

    @staticmethod
    async def get_following(db: AsyncSession, user_id: int) -> list[User]:
        """Отримати список користувачів, на яких підписаний user_id"""
        stmt = (
            select(User)
            .join(Subscription, Subscription.target_user_id == User.id)
            .where(Subscription.user_id == user_id)
        )
        result = await db.execute(stmt)
        return result.scalars().all()

    @staticmethod
    async def get_user_stats(db: AsyncSession, user_id: int) -> dict:
        """Повертає кількість followers та following для user_id"""

        followers_query = select(func.count(Subscription.id)).where(
            Subscription.target_user_id == user_id
        )
        followers_res = await db.execute(followers_query)
        followers_count = followers_res.scalar() or 0

        following_query = select(func.count(Subscription.id)).where(
            Subscription.user_id == user_id
        )
        following_res = await db.execute(following_query)
        following_count = following_res.scalar() or 0

        return {
            "followers_count": followers_count,
            "following_count": following_count
        }