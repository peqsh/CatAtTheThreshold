from sqlalchemy import BigInteger, Boolean, Float, String, DateTime, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from datetime import datetime
from typing import Optional

from app.database import Base



class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True, index=True)
    telegram_id: Mapped[Optional[int]] = mapped_column(BigInteger, unique=True, nullable=True, index=True)
    
    # Поля для веб-интерфейса
    username: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(20), default="user") # "user" или "admin"
    
    # Двухфакторная аутентификация (2FA)
    otp_secret: Mapped[str] = mapped_column(String(32)) 
    is_2fa_enabled: Mapped[bool] = mapped_column(Boolean, default=False) # Исправлено здесь!
    
    # Управление уведомлениями
    is_active: Mapped[bool] = mapped_column(Boolean, default=True) 
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())

class Detection(Base):
    __tablename__ = "detections"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), 
        server_default=func.now()
    )
    photo_url: Mapped[Optional[str]] = mapped_column(String)
    confidence_score: Mapped[float] = mapped_column(Float)