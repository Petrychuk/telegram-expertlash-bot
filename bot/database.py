#database.py
import os
import enum
from config import ADMIN_IDS
from datetime import datetime, timedelta  
from sqlalchemy import (
    create_engine, Column, Integer, String, Float, Text,
    Boolean, DateTime, BigInteger, SmallInteger, ForeignKey,
    UniqueConstraint, or_, func, Enum
)
from sqlalchemy.orm import sessionmaker, declarative_base, relationship
from dotenv import load_dotenv
    
# Загрузка переменных окружения
load_dotenv()
# --- Подключение к БД ---
# Основные имена
DB_USER = os.getenv("DB_USER") or os.getenv("user")
DB_PASSWORD = os.getenv("DB_PASSWORD") or os.getenv("password")
DB_HOST = os.getenv("DB_HOST") or os.getenv("host")
DB_PORT = os.getenv("DB_PORT") or os.getenv("port")
DB_NAME = os.getenv("DB_NAME") or os.getenv("dbname")

if not all([DB_USER, DB_PASSWORD, DB_HOST, DB_PORT, DB_NAME]):
    raise RuntimeError("Database env vars are missing. Check DB_USER/DB_PASSWORD/DB_HOST/DB_PORT/DB_NAME")

DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
engine = create_engine(DATABASE_URL, pool_pre_ping=True)

# Настройка SQLAlchemy
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# ------------------------
# Model users
# ------------------------
class UserRole(enum.Enum):
    student = "student"
    admin = "admin"
    dev = "developer"
    
class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    telegram_id = Column(BigInteger, unique=True, index=True, nullable=False)
    username = Column(String, nullable=True)
    first_name = Column(String, nullable=True)
    last_name = Column(String, nullable=True)
    role = Column(Enum(UserRole), default=UserRole.student, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Данные онбординга
    format_choice = Column(String, nullable=True)
    level_choice = Column(String, nullable=True)
    time_choice = Column(String, nullable=True)
    goal_choice = Column(String, nullable=True)
    
    subscriptions = relationship("Subscription", back_populates="user", cascade="all, delete-orphan")
    reactions = relationship("VideoReaction", back_populates="user", cascade="all, delete-orphan")
# ------------------------
# Model subscription
# ------------------------
class Subscription(Base):
    __tablename__ = "subscriptions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False) 
    telegram_id = Column(BigInteger, index=True, nullable=False) 

    # Платежная система
    payment_system = Column(String)                     # "paypal" / "stripe"
    subscription_id = Column(String, unique=True, index=True)  
    customer_id = Column(String, nullable=True)         # ID клиента (Stripe Customer, PayPal Payer)

    # Доп. идентификатор заказа/сессии
    order_id = Column(String, unique=True, index=True, nullable=True)

    # Статус
    status = Column(String, default="pending")  # pending, active, cancelled, expired, past_due
    amount = Column(Float)
    currency = Column(String, default="EUR")

    # Даты
    created_at = Column(DateTime, default=datetime.utcnow)
    activated_at = Column(DateTime, nullable=True)
    expires_at = Column(DateTime, nullable=True)
    cancelled_at = Column(DateTime, nullable=True)

    # Доступ к группе
    has_group_access = Column(Boolean, default=False)
    group_joined_at = Column(DateTime, nullable=True)
    
    # анти-спам и напоминания
    last_nudge_at   = Column(DateTime, nullable=True)   # когда последний раз пинали pending
    nudges_count    = Column(Integer, default=0)        # сколько раз пинали pending
    last_warned_at  = Column(DateTime, nullable=True)   # когда последний раз предупреждали активную о скором окончании
    
    user = relationship("User", back_populates="subscriptions")

# =========================
# CONTENT: MODULES & VIDEOS
# =========================
class Module(Base):
    __tablename__ = "modules"

    id = Column(Integer, primary_key=True)
    slug = Column(String, unique=True, index=True, nullable=False)   # "basics", "advanced-1" и т.п.
    title = Column(String, nullable=False)                           # «Модуль 1. Основы»
    description = Column(Text, nullable=True)
    position = Column(Integer, default=0, index=True)                # порядок
    is_free = Column(Boolean, default=False)                         # бесплатный (доступен без подписки)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    videos = relationship("Video", back_populates="module", cascade="all, delete-orphan")

class Video(Base):
    __tablename__ = "videos"

    id = Column(Integer, primary_key=True)
    module_id = Column(Integer, ForeignKey("modules.id", ondelete="CASCADE"), index=True, nullable=False)
    title = Column(String, nullable=False)
    # где хранится видео: либо Telegram file_id, либо внешний url
    tg_file_id = Column(String, nullable=True)   # если видео уже загружено в TG
    url       = Column(String, nullable=True)    # если храним где-то еще (CDN/Storage)
    duration_sec = Column(Integer, nullable=True)
    position = Column(Integer, default=0, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    module = relationship("Module", back_populates="videos")
    reactions = relationship("VideoReaction", back_populates="video", cascade="all, delete-orphan")

# =========================
# REACTIONS: LIKE & RATING
# =========================
class VideoReaction(Base):
    """
    Унифицированная реакция: и лайк, и рейтинг в одной строке.
    Уникальность по (video_id, user_id).
    """
    __tablename__ = "video_reactions"
    __table_args__ = (UniqueConstraint("video_id", "user_id", name="uq_reaction_video_user"),)

    id = Column(Integer, primary_key=True)
    video_id = Column(Integer, ForeignKey("videos.id", ondelete="CASCADE"), index=True, nullable=False)
    user_id  = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)

    liked = Column(Boolean, default=False)                 # лайк/анлайк
    rating = Column(SmallInteger, nullable=True)           # 1..5
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    user = relationship("User", back_populates="reactions")
    video = relationship("Video", back_populates="reactions")

# Создание таблиц
def create_tables():
    Base.metadata.create_all(bind=engine)

# Получение сессии
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()       
# ------------------------
# Users
# ------------------------
def get_user_by_telegram_id(db, telegram_id: int):
    return db.query(User).filter(User.telegram_id == telegram_id).first()

def create_user(
    db,
    telegram_id: int,
    username: str = None,
    first_name: str = None,
    last_name: str = None,
    role: str = None
):
    # если роль не указана → проверяем ADMIN_IDS
    if role is None:
        role = UserRole.admin if str(telegram_id) in [str(x) for x in ADMIN_IDS] else UserRole.student

    user = User(
        telegram_id=telegram_id,
        username=username,
        first_name=first_name,
        last_name=last_name,
        role=role
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user

def update_user_onboarding(db, telegram_id: int, format_choice: str, level_choice: str, time_choice: str, goal_choice: str):
    user = get_user_by_telegram_id(db, telegram_id)
    if user:
        user.format_choice = format_choice
        user.level_choice = level_choice
        user.time_choice = time_choice
        user.goal_choice = goal_choice
        db.commit()
        db.refresh(user)
    return user

# =========================
# SUBS HELPERS
# =========================
def create_subscription(db, user_id: int, payment_system: str, subscription_id: str, order_id: str, amount: float, customer_id: str = None):
    """
    Создаёт запись подписки в статусе pending, используя внутренний user_id.
    """
    # Находим пользователя по его внутреннему ID
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        # Эта ситуация маловероятна, но лучше ее обработать
        return None

    sub = Subscription(
        user_id=user.id,
        telegram_id=user.telegram_id, # Сохраняем для удобства отправки уведомлений
        payment_system=payment_system,
        subscription_id=subscription_id,
        order_id=order_id,
        customer_id=customer_id,
        amount=amount,
        status="pending"
    )
    db.add(sub)
    db.commit()
    db.refresh(sub)
    return sub

def activate_subscription(db, user_id: int, order_id: str, amount: float = None, currency: str = None):
    """
    Активирует подписку пользователя по его внутреннему user_id и order_id.
    Это надежный способ, так как он точно связывает платеж с конкретным пользователем.
    :param db: Сессия базы данных.
    :param user_id: Внутренний ID пользователя (из таблицы users).
    :param order_id: Уникальный ID заказа/сессии от платежной системы (Stripe session_id, PayPal order_id и т.д.).
    :param amount: Сумма платежа (опционально, для обновления).
    :param currency: Валюта платежа (опционально, для обновления).
    """
    # 1. Ищем подписку, которая была создана для этого пользователя и этого заказа.
    #    Это самый точный и надежный способ найти нужную запись.
    subscription = db.query(Subscription).filter(
        Subscription.user_id == user_id,
        or_(
            Subscription.order_id == str(order_id),
            Subscription.subscription_id == str(order_id)
        )
    ).order_by(Subscription.created_at.desc()).first()

    # Фоллбэк: если по какой-то причине order_id не совпал (редкий случай),
    # ищем последнюю неактивную подписку этого пользователя.
    if not subscription:
        subscription = db.query(Subscription).filter(
            Subscription.user_id == user_id,
            Subscription.status == "pending"
        ).order_by(Subscription.created_at.desc()).first()

    # Если подписка так и не найдена, значит что-то пошло не так.
    if not subscription:
        # Можно добавить логирование, чтобы отследить такие случаи
        # logging.error(f"Could not find subscription to activate for user_id={user_id} and order_id={order_id}")
        return None

    # 2. Активируем подписку, обновляя ее поля.
    now = datetime.utcnow()
    subscription.status = "active"
    
    # Устанавливаем дату активации только один раз
    if not subscription.activated_at:
        subscription.activated_at = now

    # Рассчитываем дату окончания от даты активации
    subscription.expires_at = subscription.activated_at + timedelta(days=30)
    
    subscription.has_group_access = True
    if not subscription.group_joined_at:
        subscription.group_joined_at = now

    # Обновляем сумму и валюту, если они были переданы
    if amount is not None:
        subscription.amount = amount
    if currency is not None:
        subscription.currency = currency

    # 3. Сохраняем изменения в базе данных.
    db.commit()
    db.refresh(subscription)
    
    return subscription

def cancel_subscription(db, subscription_id: str):
    sub = db.query(Subscription).filter(Subscription.subscription_id == subscription_id).first()
    if sub:
        sub.status = "cancelled"
        sub.cancelled_at = datetime.utcnow()
        sub.has_group_access = False
        db.commit()
        db.refresh(sub)
    return sub

def get_active_subscription(db, user_id: int): 
    """
    Ищет активную подписку для пользователя по его внутреннему ID.
    """
    now = datetime.utcnow()
    return db.query(Subscription).filter(
        Subscription.user_id == user_id,     
        Subscription.status == "active",
        Subscription.expires_at > now
    ).first()

def get_subscription_by_id(db, subscription_id: str):
    """Поиск строго по subscription_id (sub_... или PayPal id)."""
    return db.query(Subscription).filter(Subscription.subscription_id == subscription_id).first()

def get_subscription_by_any(db, key: str):
    """Поиск по subscription_id ИЛИ order_id (удобно при reconciliation Stripe)."""
    return db.query(Subscription).filter(
        or_(
            Subscription.subscription_id == str(key),
            Subscription.order_id == str(key),
        )
    ).first()

def user_has_access(db, telegram_id: int) -> bool:
    """
    Правильная проверка доступа: находит пользователя по telegram_id,
    а затем ищет активную подписку по его внутреннему user.id.
    """
    user = get_user_by_telegram_id(db, telegram_id)
    if not user:
        return False
    # Вызываем get_active_subscription с правильным user.id
    return get_active_subscription(db, user.id) is not None

# =========================
# CONTENT HELPERS (MODULES/VIDEOS)
# =========================
def upsert_module(db, *, slug: str, title: str, description: str | None = None, position: int = 0, is_free: bool = False):
    m = db.query(Module).filter_by(slug=slug).first()
    if not m:
        m = Module(slug=slug, title=title, description=description, position=position, is_free=is_free)
        db.add(m)
    else:
        m.title = title
        m.description = description
        m.position = position
        m.is_free = is_free
    db.commit()
    db.refresh(m)
    return m

def upsert_video(db, *, module_id: int, title: str, position: int = 0, tg_file_id: str | None = None, url: str | None = None, duration_sec: int | None = None):
    v = db.query(Video).filter_by(module_id=module_id, title=title).first()
    if not v:
        v = Video(module_id=module_id, title=title, position=position, tg_file_id=tg_file_id, url=url, duration_sec=duration_sec)
        db.add(v)
    else:
        v.position = position
        v.tg_file_id = tg_file_id
        v.url = url
        v.duration_sec = duration_sec
    db.commit()
    db.refresh(v)
    return v

def list_modules_for_user(db, telegram_id: int):
    """
    Возвращает модули с флагом locked:
      - locked = False если module.is_free или у пользователя активная подписка
      - locked = True  иначе
    """
    subscribed = user_has_access(db, telegram_id)
    rows = db.query(Module).order_by(Module.position.asc(), Module.id.asc()).all()
    result = []
    for m in rows:
        result.append({
            "id": m.id,
            "slug": m.slug,
            "title": m.title,
            "description": m.description,
            "position": m.position,
            "is_free": m.is_free,
            "locked": (not m.is_free) and (not subscribed)
        })
    return result

def list_videos_for_user(db, module_id: int, telegram_id: int):
    """
    Проверяем доступ к модулю. Если модуль не free и нет подписки — вернём пустой список или можешь бросать исключение.
    """
    module = db.query(Module).filter_by(id=module_id).first()
    if not module:
        return []

    if not module.is_free and not user_has_access(db, telegram_id):
        # нет доступа
        return []

    videos = db.query(Video).filter_by(module_id=module_id).order_by(Video.position.asc(), Video.id.asc()).all()

    # прикрутим агрегаты (лайки/рейтинг)
    video_ids = [v.id for v in videos] or [-1]
    likes_map = dict(
        db.query(VideoReaction.video_id, func.sum(func.case((VideoReaction.liked == True, 1), else_=0)))
          .filter(VideoReaction.video_id.in_(video_ids))
          .group_by(VideoReaction.video_id)
          .all()
    )
    rating_map = dict(
        db.query(VideoReaction.video_id, func.avg(VideoReaction.rating), func.count(VideoReaction.rating))
          .filter(VideoReaction.video_id.in_(video_ids))
          .group_by(VideoReaction.video_id)
          .all()
    )

    # реакция текущего юзера
    me_reactions = dict(
        db.query(VideoReaction.video_id, VideoReaction.liked, VideoReaction.rating)
          .join(User, User.id == VideoReaction.user_id)
          .filter(User.telegram_id == telegram_id, VideoReaction.video_id.in_(video_ids))
          .all()
    )

    out = []
    for v in videos:
        avg, cnt = rating_map.get(v.id, (None, 0))
        liked = None
        rating = None
        if v.id in me_reactions:
            # me_reactions[v.id] = (liked, rating)
            liked, rating = me_reactions[v.id]
        out.append({
            "id": v.id,
            "module_id": v.module_id,
            "title": v.title,
            "tg_file_id": v.tg_file_id,
            "url": v.url,
            "duration_sec": v.duration_sec,
            "position": v.position,
            "likes_count": int(likes_map.get(v.id, 0) or 0),
            "rating_avg": float(avg) if avg is not None else None,
            "rating_count": int(cnt or 0),
            "my_liked": bool(liked) if liked is not None else False,
            "my_rating": int(rating) if rating is not None else None,
        })
    return out

# =========================
# REACTIONS HELPERS
# =========================
MIN_RATING = 1
MAX_RATING = 5

def _ensure_user(db, telegram_id: int) -> User | None:
    u = get_user_by_telegram_id(db, telegram_id)
    if not u:
        return None
    return u

def toggle_like(db, video_id: int, telegram_id: int) -> bool | None:
    """
    Переключает лайк. Возвращает текущее состояние (True = лайк стоит).
    """
    user = _ensure_user(db, telegram_id)
    if not user:
        return None

    r = db.query(VideoReaction).filter_by(video_id=video_id, user_id=user.id).first()
    if not r:
        r = VideoReaction(video_id=video_id, user_id=user.id, liked=True)
        db.add(r)
    else:
        r.liked = not bool(r.liked)
    db.commit()
    db.refresh(r)
    return bool(r.liked)

def set_rating(db, video_id: int, telegram_id: int, rating: int) -> int | None:
    """
    Ставит/обновляет рейтинг 1..5. Возвращает установленное значение.
    """
    if rating is None:
        return None
    rating = int(rating)
    if rating < MIN_RATING or rating > MAX_RATING:
        raise ValueError(f"rating must be in [{MIN_RATING}..{MAX_RATING}]")

    user = _ensure_user(db, telegram_id)
    if not user:
        return None

    r = db.query(VideoReaction).filter_by(video_id=video_id, user_id=user.id).first()
    if not r:
        r = VideoReaction(video_id=video_id, user_id=user.id, rating=rating, liked=False)
        db.add(r)
    else:
        r.rating = rating
    db.commit()
    db.refresh(r)
    return int(r.rating)

def get_video_meta(db, video_id: int):
    """
    Возвращает агрегаты по видео: likes_count, rating_avg, rating_count.
    """
    likes = db.query(func.sum(func.case((VideoReaction.liked == True, 1), else_=0))).filter(VideoReaction.video_id == video_id).scalar() or 0
    avg, cnt = db.query(func.avg(VideoReaction.rating), func.count(VideoReaction.rating)).filter(VideoReaction.video_id == video_id).first()
    return {
        "likes_count": int(likes),
        "rating_avg": float(avg) if avg is not None else None,
        "rating_count": int(cnt or 0)
    }
