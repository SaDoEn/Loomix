from fastapi import APIRouter, Depends, UploadFile, File, Form, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Optional, List
from sqlalchemy import select, delete, or_, update, func
from app.models.interactions import Like

from app.models.media import Media
from app.api.deps import get_current_user, get_db
from app.db.session import SessionLocal
from app.schemas.media import MediaResponse
from app.storage.s3 import storage
from app.services.media import MediaService
from app.models.user import User

router = APIRouter(prefix="/media", tags=["media"])

@router.post("/upload-avatar", response_model=MediaResponse, status_code=status.HTTP_201_CREATED)
async def upload_avatar(
        file: UploadFile = File(...),
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db),
):
    """Завантаження або оновлення аватарки."""
    if not file.content_type.startswith("image/"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Аватаркою може бути тільки зображення"
        )

    # Знімаємо прапорець is_avatar зі старих аватарок користувача
    await db.execute(
        update(Media)
        .where(Media.owner_id == current_user.id, Media.is_avatar == True)
        .values(is_avatar=False)
    )

    media = await MediaService.create_user_media(
        db=db, file=file, user_id=current_user.id, is_avatar=True
    )
    return media

@router.post("/upload-post", response_model=MediaResponse, status_code=status.HTTP_201_CREATED)
async def upload_post(
        file: UploadFile = File(...),
        title: Optional[str] = Form(None),
        description: Optional[str] = Form(None),
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db) # <-- Змінили на get_db
):
    """Створення нового поста (картинка або відео) з описом."""
    if not (file.content_type.startswith("image/") or file.content_type.startswith("video/")):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Дозволені лише зображення або відео"
        )

    media = await MediaService.create_user_media(
        db=db, file=file, user_id=current_user.id, is_avatar=False, title=title, description=description
    )
    return media

@router.get("/my-posts", response_model=List[MediaResponse])
async def get_my_posts(
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db)
):
    """Отримання всіх постів поточного користувача."""
    result = await db.execute(
        select(Media).where(Media.owner_id == current_user.id, Media.is_avatar == False).order_by(Media.created_at.desc())
    )
    posts = result.scalars().all()
    return await attach_likes(db, posts, current_user)

@router.delete("/delete-post/{post_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_post(
        post_id: int,
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db)
):
    """Видалення поста користувача."""
    result = await db.execute(select(Media).where(Media.id == post_id))
    post = result.scalars().first()

    if not post:
        raise HTTPException(status_code=404, detail="Пост не знайдено")

    if post.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="У вас немає прав на видалення цього поста")

    await storage.delete_file(post.file_url)

    await db.delete(post)
    await db.commit()

    return None

@router.get("/get-avatar", response_model=Optional[MediaResponse])
async def get_my_avatar(
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db)
):
    """Отримання поточної аватарки користувача."""
    result = await db.execute(
        select(Media)
        .where(Media.owner_id == current_user.id, Media.is_avatar == True)
        .order_by(Media.created_at.desc())  # <-- Обов'язково додаємо сортування
    )
    return result.scalars().first()

async def attach_likes(db, posts, current_user):
    ids = [p.id for p in posts]
    counts = await db.execute(
        select(Like.media_id, func.count()).where(Like.media_id.in_(ids)).group_by(Like.media_id)
    )
    likes_count = dict(counts.all())
    mine = await db.execute(
        select(Like.media_id).where(Like.user_id == current_user.id, Like.media_id.in_(ids))
    )
    liked_ids = set(mine.scalars().all())
    for p in posts:
        p.likes_count = likes_count.get(p.id, 0)
        p.is_liked = p.id in liked_ids
    return posts

@router.get("/user-posts/{user_id}", response_model=List[MediaResponse])
async def get_user_posts(
        user_id: int,
        db: AsyncSession = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    stmt = select(Media).where(
        (Media.owner_id == user_id) &
        or_(Media.is_avatar == False, Media.is_avatar.is_(None))
    ).order_by(Media.created_at.desc())

    posts = (await db.execute(stmt)).scalars().all()
    return await attach_likes(db, posts, current_user)