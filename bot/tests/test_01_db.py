# tests/test_01_database.py

import pytest
from datetime import datetime, timedelta

# Импортируем все необходимые функции и модели
from database import (
    create_user, get_user_by_telegram_id,
    create_subscription, activate_subscription, cancel_subscription,
    get_active_subscription, User
)

# --- Тестовые данные ---
TEST_TG_ID = 123456789
TEST_ORDER_ID = "test_order_123"

def test_create_user(db_session):
    """Тест: функция create_user должна правильно создавать пользователя."""
    user = create_user(db_session, telegram_id=TEST_TG_ID, username="testuser")
    
    assert user is not None
    assert user.id is not None
    assert user.telegram_id == TEST_TG_ID
    assert user.username == "testuser"
    assert user.role == "student" # По умолчанию

def test_get_user_by_telegram_id(db_session):
    """Тест: функция get_user_by_telegram_id должна находить созданного пользователя."""
    create_user(db_session, telegram_id=TEST_TG_ID)
    
    found_user = get_user_by_telegram_id(db_session, TEST_TG_ID)
    assert found_user is not None
    assert found_user.telegram_id == TEST_TG_ID

def test_subscription_full_cycle(db_session):
    """
    E2E Тест: Полный жизненный цикл подписки в базе данных.
    Создание -> Активация -> Проверка -> Отмена -> Проверка.
    """
    # 1. Сначала создаем пользователя
    user = create_user(db_session, telegram_id=TEST_TG_ID)
    user_id = user.id

    # 2. Создаем подписку в статусе 'pending'
    pending_sub = create_subscription(
        db_session,
        user_id=user_id,
        payment_system="stripe",
        subscription_id=TEST_ORDER_ID,
        order_id=TEST_ORDER_ID,
        amount=29.99
    )
    assert pending_sub.status == "pending"
    assert pending_sub.user_id == user_id

    # 3. Активируем подписку
    activated_sub = activate_subscription(db_session, user_id=user_id, order_id=TEST_ORDER_ID)
    assert activated_sub is not None
    assert activated_sub.status == "active"
    assert activated_sub.expires_at > datetime.utcnow()

    # 4. Проверяем, что get_active_subscription находит ее
    active_check = get_active_subscription(db_session, user_id=user_id)
    assert active_check is not None
    assert active_check.id == activated_sub.id

    # 5. Отменяем подписку
    cancelled_sub = cancel_subscription(db_session, subscription_id=TEST_ORDER_ID)
    assert cancelled_sub is not None
    assert cancelled_sub.status == "cancelled"

    # 6. Проверяем, что теперь get_active_subscription не находит ее
    final_check = get_active_subscription(db_session, user_id=user_id)
    assert final_check is None
