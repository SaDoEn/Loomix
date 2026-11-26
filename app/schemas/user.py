from pydantic import BaseModel, EmailStr, ConfigDict, field_validator
from typing import Optional
import re

class UserCreate(BaseModel):
    email: EmailStr
    username: str
    tag: str
    password: str

    @field_validator('tag')
    @classmethod
    def check_tag(cls, v):
        v = v.strip().lower()
        if (not re.fullmatch(r'[a-z0-9_.]{3,20}', v)
                or v.startswith('.') or v.endswith('.') or '..' in v):
            raise ValueError('Тег: 3–20 символів: a-z, 0-9, _ і . (крапка не на краях і не подвійна)')
        return v

class UserResponse(BaseModel):
    id: int
    email: EmailStr
    username: str
    tag: str
    is_active: bool
    followers_count: int = 0
    following_count: int = 0

    model_config = ConfigDict(from_attributes=True)

class UserPublicProfile(BaseModel):
    id: int
    username: str
    tag: str
    avatar_url: Optional[str] = None
    followers_count: int = 0
    following_count: int = 0
    is_following: bool = False

    model_config = ConfigDict(from_attributes=True)

class UserBrief(BaseModel):
    id: int
    username: str
    tag: str

    model_config = ConfigDict(from_attributes=True)