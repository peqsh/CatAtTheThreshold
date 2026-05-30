import os
import logging
from aiogram import Bot, Dispatcher, types
from aiogram.filters import CommandStart
from aiogram.types import FSInputFile
from dotenv import load_dotenv

# absolute imports
from app.database import SessionLocal
from app.models import User
from sqlalchemy.orm import Session

load_dotenv()

TOKEN = os.getenv("TELEGRAM_TOKEN")
if not TOKEN:
    logging.error("TELEGRAM_TOKEN not found in .env file!")

bot = Bot(token=TOKEN)
dp = Dispatcher()

# HANDLERS

@dp.message(CommandStart())
async def command_start_handler(message: types.Message):
    tg_id = message.from_user.id
    db: Session = SessionLocal()
    
    try:
        user = db.query(User).filter(User.telegram_id == tg_id).first()
        if not user:
            new_user = User(telegram_id=tg_id, is_active=True)
            db.add(new_user)
            db.commit()
            db.refresh(new_user)
            print(f"DEBUG: User {tg_id} saved to DB successfully!")
            await message.answer("Success! You are now subscribed to cat notifications ??")
        else:
            user.is_active = True
            db.commit()
            await message.answer("Welcome back! Notifications are enabled.")
    except Exception as e:
        logging.error(f"Error saving user: {e}")
        await message.answer("Database error occurred.")
    finally:
        db.close()

# NOTIFICATION LOGIC

async def send_cat_notification(photo_path: str, confidence: float):
    db: Session = SessionLocal()
    try:
        active_users = db.query(User).filter(User.is_active == True, User.telegram_id.isnot(None)).all()
        
        if not active_users:
            logging.info("No active users to notify.")
            return

        photo = FSInputFile(photo_path)
        caption = f"?? Cat detected!\nConfidence: {confidence:.2%}"

        for user in active_users:
            # ПОДСТРАХОВКА: Проверяем, что ID физически существует перед отправкой
            if not user.telegram_id:
                logging.warning(f"Skipping user {user.id} because telegram_id is None")
                continue
                
            try:
                await bot.send_photo(
                    chat_id=int(user.telegram_id), # Явно приводим к числу
                    photo=photo,
                    caption=caption
                )
            except Exception as e:
                logging.warning(f"Failed to send to {user.telegram_id}: {e}")
    finally:
        db.close()

async def start_bot():
    logging.info("Bot started")
    await dp.start_polling(bot)