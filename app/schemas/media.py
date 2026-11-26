from pydantic import BaseModel
from datetime import datetime
from typing import Optional

class MediaResponse(BaseModel):
    id: int
    title: Optional[str] = None
    description: Optional[str] = None
    file_url: str
    file_type: str
    is_avatar: bool
    created_at: datetime
    likes_count: int = 0
    is_liked: bool = False

    class Config:
        from_attributes = True