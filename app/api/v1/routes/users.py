from fastapi import APIRouter, HTTPException, Depends, status, Query
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import delete, or_
from typing import List

from app.api.deps import get_current_user
from app.db.session import SessionLocal
from app.models.user import User
from app.models.media import Media
from app.models.subscriptions import Subscription
from app.models.interactions import CloseFriend  # Переконайся, що модель CloseFriend імпортована
from app.schemas.user import UserCreate, UserResponse, UserPublicProfile
from app.services.subscription import SubscriptionService
from app.core.security import get_password_hash as hash_password, verify_password, create_access_token

router = APIRouter(tags=["users"])


async def get_db():
    async with SessionLocal() as session:
        yield session


async def get_user_avatar_url(db: AsyncSession, user_id: int) -> str | None:
    """Допоміжна функція для пошуку актуальної аватарки користувача"""
    stmt = select(Media.file_url).where(
        Media.owner_id == user_id,
        Media.is_avatar == True
    ).order_by(Media.created_at.desc())
    res = await db.execute(stmt)
    return res.scalars().first()


@router.post("/register", response_model=UserResponse)
async def register_user(user_in: UserCreate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == user_in.email))
    if result.scalars().first():
        raise HTTPException(status_code=400, detail="User with this email already exists")

    tag_taken = await db.execute(select(User).where(User.tag == user_in.tag))
    if tag_taken.scalars().first():
        raise HTTPException(status_code=400, detail="Цей тег уже зайнятий")

    new_user = User(
        email=user_in.email,
        username=user_in.username,
        tag=user_in.tag,
        hashed_password=hash_password(user_in.password),
    )

    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)

    return new_user


@router.post("/login")
async def login(
        form_data: OAuth2PasswordRequestForm = Depends(),
        db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(User).where(User.email == form_data.username))
    user = result.scalars().first()

    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token = create_access_token(data={"sub": user.email})

    return {"access_token": access_token, "token_type": "bearer"}


@router.get("/me", response_model=UserResponse)
async def read_users_me(
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db)
):
    """Отримати профіль поточного авторизованого користувача зі статистикою"""
    stats = await SubscriptionService.get_user_stats(db, current_user.id)
    avatar_url = await get_user_avatar_url(db, current_user.id)

    return UserResponse(
        id=current_user.id,
        email=current_user.email,
        username=current_user.username,
        tag=current_user.tag,
        avatar_url=avatar_url,
        is_active=current_user.is_active,
        followers_count=stats["followers_count"],
        following_count=stats["following_count"]
    )


@router.get("/search", response_model=List[UserPublicProfile])
async def search_users(
        q: str = Query(..., min_length=1),
        db: AsyncSession = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    """Пошук користувачів за username або tag"""
    term = q.lstrip('@').strip()
    if not term:
        return []

    safe = term.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_')
    pattern = f"%{safe}%"
    stmt = select(User).where(
        or_(User.username.ilike(pattern, escape='\\'), User.tag.ilike(pattern, escape='\\')),
        User.id != current_user.id
    ).limit(24)

    result = await db.execute(stmt)
    users = result.scalars().all()

    results = []
    for user in users:
        sub_stmt = select(Subscription).where(
            Subscription.user_id == current_user.id,
            Subscription.target_user_id == user.id
        )
        sub_res = await db.execute(sub_stmt)
        is_following = sub_res.scalar_one_or_none() is not None

        stats = await SubscriptionService.get_user_stats(db, user.id)
        avatar_url = await get_user_avatar_url(db, user.id)

        results.append(UserPublicProfile(
            id=user.id,
            username=user.username,
            tag=user.tag,
            avatar_url=avatar_url,
            followers_count=stats["followers_count"],
            following_count=stats["following_count"],
            is_following=is_following
        ))

    return results


@router.get("/{user_id}", response_model=UserPublicProfile)
async def get_user_profile(
        user_id: int,
        db: AsyncSession = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    """Отримати публічний профіль користувача зі статистикою та статусом підписки"""
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalars().first()

    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    sub_stmt = select(Subscription).where(
        Subscription.user_id == current_user.id,
        Subscription.target_user_id == user_id
    )
    sub_res = await db.execute(sub_stmt)
    is_following = sub_res.scalar_one_or_none() is not None

    stats = await SubscriptionService.get_user_stats(db, user_id)
    avatar_url = await get_user_avatar_url(db, user_id)

    return UserPublicProfile(
        id=user.id,
        username=user.username,
        tag=user.tag,
        avatar_url=avatar_url,
        followers_count=stats["followers_count"],
        following_count=stats["following_count"],
        is_following=is_following
    )


@router.post("/{user_id}/follow")
async def follow_user(
        user_id: int,
        db: AsyncSession = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    """Підписатися на користувача"""
    if user_id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot follow yourself")

    stmt = select(Subscription).where(
        Subscription.user_id == current_user.id,
        Subscription.target_user_id == user_id
    )
    res = await db.execute(stmt)
    if res.scalar_one_or_none():
        return {"message": "Already following"}

    new_sub = Subscription(user_id=current_user.id, target_user_id=user_id)
    db.add(new_sub)
    await db.commit()
    return {"message": "Successfully followed"}


@router.post("/{user_id}/unfollow")
async def unfollow_user(
        user_id: int,
        db: AsyncSession = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    """Відписатися від користувача"""
    stmt = delete(Subscription).where(
        Subscription.user_id == current_user.id,
        Subscription.target_user_id == user_id
    )
    await db.execute(stmt)
    await db.commit()
    return {"message": "Successfully unfollowed"}


@router.post("/{user_id}/toggle-close-friend")
async def toggle_close_friend(
        user_id: int,
        db: AsyncSession = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    """Додати/Видалити користувача з Близьких друзів"""
    stmt = select(CloseFriend).where(
        CloseFriend.user_id == current_user.id,
        CloseFriend.friend_id == user_id
    )
    res = await db.execute(stmt)
    cf = res.scalar_one_or_none()

    if cf:
        await db.delete(cf)
        await db.commit()
        return {"is_close_friend": False}
    else:
        new_cf = CloseFriend(user_id=current_user.id, friend_id=user_id)
        db.add(new_cf)
        await db.commit()
        return {"is_close_friend": True}