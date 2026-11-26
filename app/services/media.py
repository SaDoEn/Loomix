from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import UploadFile
from app.storage.s3 import storage
from app.models.media import Media
from sqlalchemy import update, func
from app.models.interactions import Like

class MediaService:
    @staticmethod
    async def create_user_media(
            db: AsyncSession,
            file: UploadFile,
            user_id: int,
            is_avatar: bool = False,
            title: str = None,
            description: str = None
    ) -> Media:
        folder = "avatars" if is_avatar else "posts"
        file_type = "video" if file.content_type and file.content_type.startswith("video/") else "image"

        file_url = await storage.upload_file(file, folder=folder)

        if is_avatar:
            await db.execute(
                update(Media).where(Media.owner_id == user_id, Media.is_avatar == True).values(is_avatar=False)
            )

        db_media = Media(
            title=title if title else ("Avatar" if is_avatar else "Untitled"),
            description=description if description else ("User Profile Avatar" if is_avatar else ""),
            file_url=file_url,
            file_type=file_type,
            is_avatar=is_avatar,
            owner_id=user_id,
        )

        db.add(db_media)
        await db.commit()
        await db.refresh(db_media)

        return db_media