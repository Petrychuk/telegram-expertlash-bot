# tests/test_03_webhooks.py

import json
from unittest.mock import patch, MagicMock

# --- Тестовые данные ---
TEST_USER_ID = 55555
STRIPE_SESSION_ID = "cs_test_12345"
PAYPAL_SUB_ID = "I-ABCDEFGHIJKL"

# --- Тестовые полезные нагрузки (payloads) ---
STRIPE_PAYLOAD = {
    "id": "evt_123", "object": "event", "type": "checkout.session.completed",
    "data": {
        "object": {
            "id": STRIPE_SESSION_ID, "object": "checkout.session",
            "metadata": {"user_id": str(TEST_USER_ID)},
            "amount_total": 3000, "currency": "eur"
        }
    }
}

PAYPAL_PAYLOAD = {
    "event_type": "BILLING.SUBSCRIPTION.ACTIVATED",
    "resource": {
        "id": PAYPAL_SUB_ID,
        "custom_id": str(TEST_USER_ID)
    }
}

# Используем patch для имитации верификации подписи
@patch('payment_service.verify_stripe_webhook', return_value=STRIPE_PAYLOAD)
@patch('telegram_service.TelegramService.send_payment_success_notification', new_callable=MagicMock)
def test_stripe_webhook_success(mock_send_notification, mock_verify, client, db_session):
    """E2E Тест: Вебхук Stripe должен активировать подписку."""
    from database import create_user, create_subscription
    
    # 1. Создаем пользователя и pending подписку
    user = create_user(db_session, telegram_id=123)
    create_subscription(db_session, user_id=user.id, order_id=STRIPE_SESSION_ID, payment_system="stripe")

    # 2. Отправляем фейковый запрос на вебхук
    response = client.post(
        "/webhook/stripe",
        data=json.dumps(STRIPE_PAYLOAD),
        content_type="application/json",
        headers={"Stripe-Signature": "dummy_sig"}
    )
    
    # 3. Проверяем результат
    assert response.status_code == 200
    
    # 4. Проверяем, что подписка в БД стала активной
    from database import get_active_subscription
    active_sub = get_active_subscription(db_session, user_id=user.id)
    assert active_sub is not None
    assert active_sub.status == "active"
    
    # 5. Проверяем, что было вызвано уведомление в Telegram
    mock_send_notification.assert_called_once()

@patch('payment_service.verify_paypal_webhook', return_value=True)
@patch('telegram_service.TelegramService.send_payment_success_notification', new_callable=MagicMock)
def test_paypal_webhook_success(mock_send_notification, mock_verify, client, db_session):
    """E2E Тест: Вебхук PayPal должен активировать подписку."""
    from database import create_user, create_subscription
    
    # 1. Создаем пользователя и pending подписку
    user = create_user(db_session, telegram_id=456)
    create_subscription(db_session, user_id=user.id, order_id=PAYPAL_SUB_ID, payment_system="paypal")

    # 2. Отправляем фейковый запрос на вебхук
    response = client.post(
        "/webhook/paypal",
        data=json.dumps(PAYPAL_PAYLOAD),
        content_type="application/json",
        headers={"Some-PayPal-Header": "dummy"}
    )
    
    # 3. Проверяем результат
    assert response.status_code == 200
    
    # 4. Проверяем, что подписка в БД стала активной
    from database import get_active_subscription
    active_sub = get_active_subscription(db_session, user_id=user.id)
    assert active_sub is not None
    assert active_sub.status == "active"
    
    # 5. Проверя
