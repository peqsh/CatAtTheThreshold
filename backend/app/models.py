from sqlalchemy import BigInteger, Boolean, Float, String, DateTime, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from datetime import datetime
from typing import Optional

from app.database import Base



class User(Base):
    __tablename__ = "users"
    
    id: Mapped[int] = mapped_column(primary_key=True)

    username: Mapped[str] = mapped_column(String(50), unique=True, nullable=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=True)
    
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    

    is_admin: Mapped[bool] = mapped_column(Boolean, default=False)
    otp_secret: Mapped[Optional[str]] = mapped_column(String(32))

class Detection(Base):
    __tablename__ = "detections"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), 
        server_default=func.now()
    )
    photo_url: Mapped[Optional[str]] = mapped_column(String)
    confidence_score: Mapped[float] = mapped_column(Float)