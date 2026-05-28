# backend/init_db.py
from app.database import engine, Base
# Импортировать ВСЕ модели
from app.models import User, Detection 

def setup_database():
    print("Удаление старых таблиц...")
    Base.metadata.drop_all(bind=engine)
    
    print("Создание новых таблиц...")
    Base.metadata.create_all(bind=engine)
    print("Готово! Проверь базу в pgAdmin.")

if __name__ == "__main__":
    setup_database()