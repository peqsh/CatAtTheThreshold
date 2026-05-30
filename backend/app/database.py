import os
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from dotenv import load_dotenv

load_dotenv()

SQLALCHEMY_DATABASE_URL = os.getenv("DATABASE_URL")

engine = create_engine(SQLALCHEMY_DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

class Base(DeclarativeBase):
    pass

def get_db():
    """
    Генератор зависимости (dependency) для создания сессии СУБД.
    Автоматически открывает сессию при запросе к серверу 
    и закрывает её сразу после отправки ответа пользователю.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()