from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete, func

from app.models.user import User
from app.models.media import Media
from app.models.interactions import Like, Comment, CloseFriend
from app.api.deps import get_current_user, get_db

router = APIRouter()

@router.post("/media/{media_id}/like")
async def toggle_like(
    media_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    stmt = select(Like).where(Like.user_id == current_user.id, Like.media_id == media_id)
    result = await db.execute(stmt)
    existing_like = result.scalar_one_or_none()

    if existing_like:
        await db.delete(existing_like)
        await db.commit()
        is_liked = False
    else:
        new_like = Like(user_id=current_user.id, media_id=media_id)
        db.add(new_like)
        await db.commit()
        is_liked = True

    count_stmt = select(func.count()).select_from(Like).where(Like.media_id == media_id)
    count_res = await db.execute(count_stmt)
    total_likes = count_res.scalar() or 0

    return {"is_liked": is_liked, "likes_count": total_likes}

@router.get("/media/{media_id}/comments")
async def get_comments(
    media_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    stmt = select(Comment).where(Comment.media_id == media_id).order_by(Comment.created_at.asc())
    res = await db.execute(stmt)
    comments = res.scalars().all()

    output = []
    media_res = await db.execute(select(Media).where(Media.id == media_id))
    media = media_res.scalar_one_or_none()
    for c in comments:
        user_res = await db.execute(select(User).where(User.id == c.user_id))
        comment_owner = user_res.scalar_one_or_none()
        output.append({
            "id": c.id,
            "text": c.text,
            "username": comment_owner.username if comment_owner else "Анонім",
            "created_at": c.created_at.strftime("%H:%M %d.%m.%Y"),
            "can_delete": c.user_id == current_user.id or (Media is not None and media.owner_id == current_user.id),
        })
    return output

@router.post("/media/{media_id}/comments")
async def add_comment(
    media_id: int,
    payload: dict,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    text = payload.get("text", "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="Коментар не може бути порожнім")

    comment = Comment(user_id=current_user.id, media_id=media_id, text=text)
    db.add(comment)
    await db.commit()
    await db.refresh(comment)

    return {
        "id": comment.id,
        "text": comment.text,
        "username": current_user.username,
        "created_at": comment.created_at.strftime("%H:%M %d.%m.%Y")
    }

@router.patch("/media/{media_id}/visibility")
async def update_media_visibility(
    media_id: int,
    payload: dict, # {"is_private": bool, "is_close_friends": bool}
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    stmt = select(Media).where(Media.id == media_id, Media.owner_id == current_user.id)
    res = await db.execute(stmt)
    media = res.scalar_one_or_none()

    if not media:
        raise HTTPException(status_code=404, detail="Медіа не знайдено або немає доступу")

    if "is_private" in payload:
        media.is_private = payload["is_private"]
    if "is_close_friends" in payload:
        media.is_close_friends = payload["is_close_friends"]

    await db.commit()
    return {"message": "Видимість оновлено", "is_private": media.is_private, "is_close_friends": media.is_close_friends}

@router.post("/users/{target_id}/toggle-close-friend")
async def toggle_close_friend(
    target_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    stmt = select(CloseFriend).where(CloseFriend.user_id == current_user.id, CloseFriend.friend_id == target_id)
    res = await db.execute(stmt)
    cf = res.scalar_one_or_none()

    if cf:
        await db.delete(cf)
        await db.commit()
        return {"is_close_friend": False}
    else:
        new_cf = CloseFriend(user_id=current_user.id, friend_id=target_id)
        db.add(new_cf)
        await db.commit()
        return {"is_close_friend": True}

@router.delete("/media/{media_id}/comments/{comment_id}")
async def delete_comment(
        media_id: int,
        comment_id: int,
        db: AsyncSession = Depends(get_db),
        current_user: User = Depends(get_current_user)
):
    res = await db.execute(select(Comment).where(Comment.id == comment_id, Comment.media_id == media_id))
    comment = res.scalar_one_or_none()
    if not comment:
        raise HTTPException(status_code=404, detail="Коментар не знайдено")

    media = (await db.execute(select(Media).where(Media.id == media_id))).scalar_one_or_none()
    if comment.user_id != current_user.id and (media is None or media.owner_id != current_user.id):
        raise HTTPException(status_code=403, detail="Немає права видалити цей коментар")

    await db.delete(comment)
    await db.commit()
    return {"deleted": True}