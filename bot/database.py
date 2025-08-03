from sqlalchemy import create_engine, Column, Integer, String, DateTime, Boolean, Float
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime, timedelta
import os

# Настройка базы данных
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATABASE_URL = f"sqlite:///{os.path.join(BASE_DIR, 'subscriptions.db')}"
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

print(f"Using database at: {DATABASE_URL}")

class User(Base):
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    telegram_id = Column(Integer, unique=True, index=True)
    username = Column(String, nullable=True)
    first_name = Column(String, nullable=True)
    last_name = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Данные онбординга
    format_choice = Column(String, nullable=True)
    level_choice = Column(String, nullable=True)
    time_choice = Column(String, nullable=True)
    goal_choice = Column(String, nullable=True)

class Subscription(Base):
    __tablename__ = "subscriptions"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, index=True)  # Связь с User.id
    telegram_id = Column(Integer, index=True)  # Дублируем для быстрого поиска
    
    # Платежная система
    payment_system = Column(String)  # "paypal" или "stripe"
    subscription_id = Column(String, unique=True, index=True)  # ID подписки в платежной системе
    customer_id = Column(String, nullable=True)  # ID клиента в платежной системе
    
    # Статус подписки
    status = Column(String, default="pending")  # pending, active, cancelled, expired
    amount = Column(Float)  # Сумма подписки
    currency = Column(String, default="EUR")
    
    # Даты
    created_at = Column(DateTime, default=datetime.utcnow)
    activated_at = Column(DateTime, nullable=True)
    expires_at = Column(DateTime, nullable=True)
    cancelled_at = Column(DateTime, nullable=True)
    
    # Доступ к группе
    has_group_access = Column(Boolean, default=False)
    group_joined_at = Column(DateTime, nullable=True)

def create_tables():
    """Создание всех таблиц в базе данных"""
    Base.metadata.create_all(bind=engine)

def get_db():
    """Получение сессии базы данных"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def get_user_by_telegram_id(db, telegram_id: int):
    """Получение пользователя по Telegram ID"""
    return db.query(User).filter(User.telegram_id == telegram_id).first()

def create_user(db, telegram_id: int, username: str = None, first_name: str = None, last_name: str = None):
    """Создание нового пользователя"""
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
    """Обновление данных онбординга пользователя"""
    user = get_user_by_telegram_id(db, telegram_id)
    if user:
        user.format_choice = format_choice
        user.level_choice = level_choice
        user.time_choice = time_choice
        user.goal_choice = goal_choice
        db.commit()
        db.refresh(user)
    return user

def create_subscription(db, telegram_id: int, payment_system: str, subscription_id: str, amount: float, customer_id: str = None):
    """Создание новой подписки"""
    user = get_user_by_telegram_id(db, telegram_id)
    if not user:
        return None
    
    subscription = Subscription(
        user_id=user.id,
        telegram_id=telegram_id,
        payment_system=payment_system,
        subscription_id=subscription_id,
        customer_id=customer_id,
        amount=amount,
        status="pending"
    )
    db.add(subscription)
    db.commit()
    db.refresh(subscription)
    return subscription

def activate_subscription(db, subscription_id: str):
    """Активация подписки"""
    subscription = db.query(Subscription).filter(Subscription.subscription_id == subscription_id).first()
    if subscription:
        subscription.status = "active"
        subscription.activated_at = datetime.utcnow()
        subscription.expires_at = datetime.utcnow() + timedelta(days=30)  # 30 дней
        subscription.has_group_access = True
        db.commit()
        db.refresh(subscription)
    return subscription

def cancel_subscription(db, subscription_id: str):
    """Отмена подписки"""
    subscription = db.query(Subscription).filter(Subscription.subscription_id == subscription_id).first()
    if subscription:
        subscription.status = "cancelled"
        subscription.cancelled_at = datetime.utcnow()
        subscription.has_group_access = False
        db.commit()
        db.refresh(subscription)
    return subscription

def get_active_subscription(db, telegram_id: int):
    """Получение активной подписки пользователя"""
    return db.query(Subscription).filter(
        Subscription.telegram_id == telegram_id,
        Subscription.status == "active",
        Subscription.expires_at > datetime.utcnow()
    ).first()

def get_subscription_by_id(db, subscription_id: str):
    """Получение подписки по ID"""
    return db.query(Subscription).filter(Subscription.subscription_id == subscription_id).first()
