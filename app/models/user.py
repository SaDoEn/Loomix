from sqlalchemy import String, Integer, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.base import Base
from app.models.subscriptions import Subscription


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    username: Mapped[str] = mapped_column(String, unique=True, index=True, nullable=False)
    tag: Mapped[str] = mapped_column(String, unique=True, index=True, nullable=False)
    email: Mapped[str] = mapped_column(String, unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    media_uploads = relationship("Media", back_populates="owner", cascade="all, delete-orphan")

    subscriptions = relationship(
        "Subscription",
        foreign_keys=[Subscription.user_id],
        backref="subscriber",
        cascade="all, delete-orphan"
    )

    followers = relationship(
        "Subscription",
        foreign_keys=[Subscription.target_user_id],
        backref="target",
        cascade="all, delete-orphan"
    )