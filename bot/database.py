import os
from datetime import datetime, timedelta
from sqlalchemy import (
    create_engine, Column, Integer, String, Float,
    Boolean, DateTime, BigInteger, or_, text
)
from sqlalchemy.orm import sessionmaker, declarative_base
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
class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    telegram_id = Column(BigInteger, unique=True, index=True, nullable=False)
    username = Column(String, nullable=True)
    first_name = Column(String, nullable=True)
    last_name = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    # Данные онбординга
    format_choice = Column(String, nullable=True)
    level_choice = Column(String, nullable=True)
    time_choice = Column(String, nullable=True)
    goal_choice = Column(String, nullable=True)

# ------------------------
# Model subscription
# ------------------------
class Subscription(Base):
    __tablename__ = "subscriptions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, index=True) 
    telegram_id = Column(BigInteger, index=True, nullable=False) 

    # Платежная система
    payment_system = Column(String)                     # "paypal" или "stripe"
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

def create_user(db, telegram_id: int, username: str = None, first_name: str = None, last_name: str = None):
    user = User(
        telegram_id=telegram_id,
        username=username,
        first_name=first_name,
        last_name=last_name
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

# ------------------------
# subscriptio
# ------------------------
def create_subscription(db, telegram_id: int, payment_system: str, subscription_id: str, amount: float, customer_id: str = None):
    """
    Создаёт запись подписки в статусе pending.
    Для Stripe ты сейчас кладёшь сюда checkout.session.id.
    Для PayPal — реальный subscription id.
    """
    user = get_user_by_telegram_id(db, telegram_id)
    if not user:
        return None

    sub = Subscription(
        user_id=user.id,
        telegram_id=telegram_id,
        payment_system=payment_system,
        subscription_id=subscription_id,
        order_id=subscription_id,  # временно при Stripe: session_id == order_id
        customer_id=customer_id,
        amount=amount,
        status="pending"
    )
    db.add(sub)
    db.commit()
    db.refresh(sub)
    return sub


def activate_subscription(db, order_id=None, telegram_id=None, amount=None, currency=None):
    """
    Активирует подписку, пытаясь найти её по разным ключам:
      - order_id (PayPal resource.id или Stripe checkout/session id/real sub id)
      - subscription_id
      - последняя подписка пользователя (по telegram_id)
    """
    subscription = None

    # 1) Ищем по order_id И/ИЛИ subscription_id
    if order_id:
        subscription = db.query(Subscription).filter(
            or_(
                Subscription.order_id == str(order_id),
                Subscription.subscription_id == str(order_id),
            )
        ).first()

    # 2) Фоллбек: по последней подписке юзера
    if not subscription and telegram_id:
        subscription = db.query(Subscription).filter_by(telegram_id=telegram_id)\
            .order_by(Subscription.created_at.desc()).first()

    if not subscription:
        return None

    now = datetime.utcnow()
    subscription.status = "active"
    subscription.activated_at = subscription.activated_at or now
    subscription.expires_at = subscription.activated_at + timedelta(days=30)
    subscription.has_group_access = True
    subscription.group_joined_at = subscription.group_joined_at or now

    if amount is not None:
        subscription.amount = amount
    if currency is not None:
        subscription.currency = currency

    if telegram_id:
        subscription.telegram_id = telegram_id
        user = db.query(User).filter_by(telegram_id=telegram_id).first()
        if user:
            subscription.user_id = user.id

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

def get_active_subscription(db, telegram_id: int):
    return db.query(Subscription).filter(
        Subscription.telegram_id == telegram_id,
        Subscription.status == "active",
        Subscription.expires_at > datetime.utcnow()
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
