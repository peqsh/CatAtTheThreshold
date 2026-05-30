import io
import base64
import qrcode
import pyotp
from fastapi import FastAPI, Depends, Form, Request, HTTPException, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from passlib.context import CryptContext
from sqlalchemy.orm import Session
from sqlalchemy import func
import uvicorn
import bcrypt
import asyncio

# Импорты компонентов нашего приложения
from app.database import engine, Base, get_db
from app.models import User, Detection
from app.telegram import dp, bot

# Инициализируем таблицы базы данных при старте
Base.metadata.create_all(bind=engine)

app = FastAPI(title="Cat at the Threshold - Web Panel")

# Настраиваем раздачу папки static (чтобы картинки cat_*.jpg были доступны в браузере)
app.mount("/static", StaticFiles(directory="static"), name="static")

# Подключаем шаблонизатор Jinja2 для работы с HTML
templates = Jinja2Templates(directory="templates")



# --- СЛУЖЕБНЫЕ ФУНКЦИИ БЕЗОПАСНОСТИ ---

def get_password_hash(password: str) -> str:
    """Генерирует безопасный хэш из чистого текста пароля с помощью чистого bcrypt."""
    password_bytes = password.encode('utf-8')
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password_bytes, salt).decode('utf-8')

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Проверяет соответствие введенного пароля сохраненному хэшу."""
    try:
        return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))
    except Exception:
        return False

def get_current_user(request: Request, db: Session = Depends(get_db)) -> User | None:
    """
    Проверяет сессионную куку 'session_user' и вытаскивает пользователя из базы.
    Если куки нет или она поддельная — возвращает None.
    """
    username = request.cookies.get("session_user")
    if not username:
        return None
    return db.query(User).filter(User.username == username).first()


# --- МАРШРУТЫ (ROUTES) ВЕБ-ИНТЕРФЕЙСА ---

@app.get("/", response_class=HTMLResponse)
async def dashboard_page(request: Request, db: Session = Depends(get_db)):
    """Главная страница дашборда (Доступна только авторизованным)."""
    current_user = get_current_user(request, db)
    if not current_user:
        return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)

    # Собираем данные для карточек статистики
    total_users = db.query(func.count(User.id)).scalar() or 0
    active_subscriptions = db.query(func.count(User.id)).filter(User.is_active == True).scalar() or 0
    total_detections = db.query(func.count(Detection.id)).scalar() or 0

    # Загружаем последние 9 детекций кота (сортировка от новых к старым)
    detections = db.query(Detection).order_by(Detection.timestamp.desc()).limit(9).all()

    # Если вошел Администратор, загружаем список всех пользователей для таблицы управления
    all_users = []
    if current_user.role == "admin":
        all_users = db.query(User).order_by(User.created_at.desc()).all()

    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "user": current_user,
            "total_users": total_users,
            "active_subscriptions": active_subscriptions,
            "total_detections": total_detections,
            "detections": detections,
            "all_users": all_users
        }
    )


@app.get("/register", response_class=HTMLResponse)
async def register_page(request: Request):
    """Страница регистрации — генерирует новый секрет 2FA и QR-код."""
    # Генерируем случайный Base32 секретный ключ для Google Authenticator (длина 32 символа)
    otp_secret = pyotp.random_base32()
    
    # Создаем URI-ссылку, которую поймет мобильное приложение Google Authenticator
    totp_uri = pyotp.totp.TOTP(otp_secret).provisioning_uri(
        name="User", 
        issuer_name="CatThreshold"
    )

    # Генерируем картинку QR-кода прямо в оперативной памяти (без сохранения на диск)
    qr = qrcode.QRCode(version=1, box_size=10, border=4)
    qr.add_data(totp_uri)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    
    # Переводим картинку в формат Base64-строки, чтобы встроить прямо в HTML тег <img>
    buffered = io.BytesIO()
    img.save(buffered, format="PNG")
    qr_base64 = base64.b64encode(buffered.getvalue()).decode("utf-8")

    return templates.TemplateResponse(
        request=request,
        name="register.html", 
        context={
            "secret": otp_secret, 
            "qr_code": qr_base64,
            "user": None
        }
    )


@app.post("/register")
async def handle_register(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    telegram_id: int = Form(None),
    otp_secret: str = Form(...),
    verify_code: str = Form(..., alias="2fa_code"),
    db: Session = Depends(get_db)
):
    """Обработка данных формы регистрации."""
    # Проверяем, существует ли уже пользователь с таким логином
    existing_user = db.query(User).filter(User.username == username).first()
    if existing_user:
        # Перегенерируем секрет и QR-код, чтобы страница не ломалась при ошибке
        otp_secret_new = pyotp.random_base32()
        totp_uri = pyotp.totp.TOTP(otp_secret_new).provisioning_uri(name="User", issuer_name="CatThreshold")
        qr = qrcode.QRCode(version=1, box_size=10, border=4)
        qr.add_data(totp_uri)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        buffered = io.BytesIO()
        img.save(buffered, format="PNG")
        qr_base64 = base64.b64encode(buffered.getvalue()).decode("utf-8")
        
        # ИСПРАВЛЕНО: Добавлен request в начало
        return templates.TemplateResponse(
            request,
            name="register.html", 
            context={
                "error": "Пользователь с таким логином уже существует",
                "secret": otp_secret_new,
                "qr_code": qr_base64,
                "user": None
            }
        )

    # Валидация введённого 6-значного кода 2FA с помощью pyotp
    totp = pyotp.TOTP(otp_secret)
    if not totp.verify(verify_code):
        # Если код не подошел, возвращаем ошибку и новые данные для генерации
        otp_secret_new = pyotp.random_base32()
        totp_uri = pyotp.totp.TOTP(otp_secret_new).provisioning_uri(name="User", issuer_name="CatThreshold")
        qr = qrcode.QRCode(version=1, box_size=10, border=4)
        qr.add_data(totp_uri)
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        buffered = io.BytesIO()
        img.save(buffered, format="PNG")
        qr_base64 = base64.b64encode(buffered.getvalue()).decode("utf-8")

        # ИСПРАВЛЕНО: Добавлен request в начало
        return templates.TemplateResponse(
            request,
            name="register.html", 
            context={
                "error": "Неверный код 2FA. Попробуйте отсканировать заново.",
                "secret": otp_secret_new,
                "qr_code": qr_base64,
                "user": None
            }
        )

    # Если всё верно: хэшируем пароль
    hashed_password = get_password_hash(password)

    # Самый первый зарегистрированный пользователь в системе автоматически становится Админом!
    user_count = db.query(func.count(User.id)).scalar() or 0
    assigned_role = "admin" if user_count == 0 else "user"

    # Создаем запись в PostgreSQL
    new_user = User(
        username=username,
        password_hash=hashed_password,
        telegram_id=telegram_id,
        role=assigned_role,
        otp_secret=otp_secret,
        is_2fa_enabled=True
    )
    
    db.add(new_user)
    db.commit()

    # После успешной регистрации отправляем пользователя на страницу входа
    return RedirectResponse(url="/login", status_code=status.HTTP_303_SEE_OTHER)


@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    """Отображение страницы входа."""
    # ИСПРАВЛЕНО: request передан первым позиционным аргументом
    return templates.TemplateResponse(request, name="login.html", context={"user": None})


@app.post("/login")
async def handle_login(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    code_2fa: str = Form(...),
    db: Session = Depends(get_db)
):
    """Обработка авторизации (Пароль + 2FA)."""
    # Ищем пользователя в базе
    user = db.query(User).filter(User.username == username).first()
    
    # Проверяем пароль
    if not user or not verify_password(password, user.password_hash):
        # ИСПРАВЛЕНО: request передан первым позиционным аргументом
        return templates.TemplateResponse(request, name="login.html", context={"error": "Неверный логин или пароль"})

    # Проверяем 6-значный код безопасности TOTP через его личный ключ
    totp = pyotp.TOTP(user.otp_secret)
    if not totp.verify(code_2fa):
        # ИСПРАВЛЕНО: request передан первым позиционным аргументом
        return templates.TemplateResponse(request, name="login.html", context={"error": "Неверный код двухфакторной аутентификации (2FA)"})

    # Авторизация успешна! Создаем куку сессии и редиректим на дашборд
    response = RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)
    response.set_cookie(key="session_user", value=user.username, httponly=True)
    return response


@app.get("/logout")
async def logout():
    """Сброс авторизации (удаление сессионной куки)."""
    response = RedirectResponse(url="/login")
    response.delete_cookie("session_user")
    return response


# --- ИНТЕГРАЦИЯ С ТЕЛЕГРАМ-БОТОМ (STARTUP/SHUTDOWN События) ---

@app.on_event("startup")
async def startup_event():
    """Фоновый запуск Telegram-бота одновременно с сервером FastAPI."""
    import logging
    logger = logging.getLogger("uvicorn")
    logger.info("Запуск фоновой задачи интеграции с Telegram Bot API...")
    asyncio.create_task(dp.start_polling(bot))

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=True)