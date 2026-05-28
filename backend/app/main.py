import asyncio
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends
from sqlalchemy.orm import Session

# Absolute imports
from app.database import engine, SessionLocal, Base
from app.models import User
from app.telegram import dp, bot
from app import models

# Logging setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Database initialization
    logger.info("Initializing database...")
    Base.metadata.create_all(bind=engine)
    
    # Start Telegram Bot polling in background
    logger.info("Starting Telegram bot...")
    bot_task = asyncio.create_task(dp.start_polling(bot))
    
    yield
    
    # Shutdown: stop bot and close session
    logger.info("Stopping bot...")
    bot_task.cancel()
    try:
        await bot_task
    except asyncio.CancelledError:
        logger.info("Bot background task stopped.")
    await bot.session.close()

app = FastAPI(
    title="Cat Detection System API",
    lifespan=lifespan
)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.get("/")
def read_root():
    return {"status": "online", "message": "Cat monitoring system is active"}

@app.get("/stats")
def get_stats(db: Session = Depends(get_db)):
    users_count = db.query(User).count()
    active_users = db.query(User).filter(User.is_active == True).count()
    return {
        "total_users": users_count,
        "active_subscriptions": active_users
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)