import os
from datetime import datetime, timedelta

from sqlalchemy import (
    create_engine, Column, Integer, String, Float,
    Boolean, DateTime, BigInteger
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

# Загрузка переменных окружения
load_dotenv()

# Получение данных подключения из .env
DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_HOST = os.getenv("DB_HOST")
DB_PORT = os.getenv("DB_PORT")
DB_NAME = os.getenv("DB_NAME")

# Формирование строки подключения
DATABASE_URL = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
engine = create_engine(DATABASE_URL, pool_pre_ping=True)

# Настройка SQLAlchemy
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Модель пользователя
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

# Модель подписки
class Subscription(Base):
    __tablename__ = "subscriptions"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, index=True)  # Связь с User.id
    telegram_id = Column(BigInteger, unique=True, index=True, nullable=False)  # Дублируем для быстрого поиска
    
    # Платежная система
    payment_system = Column(String)  # "paypal" или "stripe"
    subscription_id = Column(String, unique=True, index=True)  # ID подписки в платёжной системе
    customer_id = Column(String, nullable=True)  # ID клиента в платёжной системе
    
    # Статус подписки
    order_id = Column(String, unique=True, index=True, nullable=True)
    status = Column(String, default="pending")  # pending, active, cancelled, expired
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

# Получение пользователя по Telegram ID
def get_user_by_telegram_id(db, telegram_id: int):
    return db.query(User).filter(User.telegram_id == telegram_id).first()

# Создание нового пользователя
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

# Обновление онбординга
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

# Создание подписки
def create_subscription(db, telegram_id: int, payment_system: str, subscription_id: str, amount: float, customer_id: str = None):
    user = get_user_by_telegram_id(db, telegram_id)
    if not user:
        return None
    
    subscription = Subscription(
        user_id=user.id,
        telegram_id=telegram_id,
        payment_system=payment_system,
        subscription_id=subscription_id,
        order_id=subscription_id,
        customer_id=customer_id,
        amount=amount,
        status="pending"
    )
    db.add(subscription)
    db.commit()
    db.refresh(subscription)
    return subscription

# Активация подписки
def activate_subscription(db, order_id=None, telegram_id=None, amount=None, currency=None):
    subscription = None
    if order_id:
        subscription = db.query(Subscription).filter(
            (Subscription.order_id == order_id) |
            (Subscription.subscription_id == order_id)
        ).first()
        
    if not subscription and telegram_id:
        subscription = db.query(Subscription).filter_by(telegram_id=telegram_id).first()

    if not subscription:
        return None

    subscription.status = "active"  # Обязательно обновить статус
    subscription.activated_at = subscription.activated_at or datetime.utcnow()
    subscription.expires_at = subscription.activated_at + timedelta(days=30)
    subscription.has_group_access = True
    subscription.group_joined_at = subscription.group_joined_at or datetime.utcnow()

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


# Отмена подписки
def cancel_subscription(db, subscription_id: str):
    subscription = db.query(Subscription).filter(Subscription.subscription_id == subscription_id).first()
    if subscription:
        subscription.status = "cancelled"
        subscription.cancelled_at = datetime.utcnow()
        subscription.has_group_access = False
        db.commit()
        db.refresh(subscription)
    return subscription

# Получение активной подписки
def get_active_subscription(db, telegram_id: int):
    return db.query(Subscription).filter(
        Subscription.telegram_id == telegram_id,
        Subscription.status == "active",
        Subscription.expires_at > datetime.utcnow()
    ).first()

# Получение подписки по ID
def get_subscription_by_id(db, subscription_id: str):
    return db.query(Subscription).filter(Subscription.subscription_id == subscription_id).first()


