# tests/test_03_webhooks.py 
import json
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta

# --- Тестовые данные ---
TEST_USER_ID = 55555
TEST_TG_ID = 123456789
STRIPE_SESSION_ID = "cs_test_12345" # ID сессии для новой подписки
STRIPE_SUB_ID = "sub_stripe_real_id" # Реальный ID подписки Stripe
PAYPAL_SUB_ID = "I-ABCDEFGHIJKL"

# --- Генераторы тестовых событий (Payloads) ---

def stripe_event(event_type, data):
    """Вспомогательная функция для создания объекта события Stripe."""
    return {"id": "evt_test_123", "object": "event", "type": event_type, "data": {"object": data}}

# Событие: Успешная первая оплата
stripe_checkout_completed = stripe_event(
    'checkout.session.completed',
    {"id": STRIPE_SESSION_ID, "object": "checkout.session", "subscription": STRIPE_SUB_ID, "metadata": {"user_id": str(TEST_USER_ID)}, "amount_total": 3000, "currency": "eur"}
)

# Событие: Успешное продление подписки
stripe_invoice_paid = stripe_event(
    'invoice.payment_succeeded',
    {"subscription": STRIPE_SUB_ID}
)

# Событие: Неудачное продление подписки
stripe_invoice_failed = stripe_event(
    'invoice.payment_failed',
    {"subscription": STRIPE_SUB_ID}
)

# Событие: Пользователь отменил подписку
stripe_subscription_deleted = stripe_event(
    'customer.subscription.deleted',
    {"id": STRIPE_SUB_ID}
)

# Событие: PayPal активировал подписку
paypal_activated = {"event_type": "BILLING.SUBSCRIPTION.ACTIVATED", "resource": {"id": PAYPAL_SUB_ID, "custom_id": str(TEST_USER_ID)}}

# Событие: PayPal отменил подписку
paypal_cancelled = {"event_type": "BILLING.SUBSCRIPTION.CANCELLED", "resource": {"id": PAYPAL_SUB_ID}}


# === Тесты для Stripe ===

@patch('payment_service.verify_stripe_webhook')
@patch('telegram_service.TelegramService.send_payment_success_notification', new_callable=MagicMock)
def test_stripe_webhook_checkout_completed(mock_send_notification, mock_verify, client, db_session):
    """Тест [Stripe]: Успешная активация новой подписки."""
    from database import create_user, create_subscription, get_active_subscription
    mock_verify.return_value = stripe_checkout_completed
    
    user = create_user(db_session, telegram_id=TEST_TG_ID)
    create_subscription(db_session, user_id=user.id, order_id=STRIPE_SESSION_ID, payment_system="stripe")

    response = client.post("/webhook/stripe", data=json.dumps(stripe_checkout_completed), content_type="application/json")
    
    assert response.status_code == 200
    active_sub = get_active_subscription(db_session, user_id=user.id)
    assert active_sub is not None
    assert active_sub.status == "active"
    assert active_sub.subscription_id == STRIPE_SUB_ID # Проверяем, что ID обновился
    mock_send_notification.assert_called_once()

@patch('payment_service.verify_stripe_webhook')
@patch('telegram_service.TelegramService.send_subscription_renewed_notification', new_callable=MagicMock)
def test_stripe_webhook_invoice_paid(mock_send_notification, mock_verify, client, db_session):
    """Тест [Stripe]: Успешное продление существующей подписки."""
    from database import create_user, create_subscription, activate_subscription
    mock_verify.return_value = stripe_invoice_paid

    user = create_user(db_session, telegram_id=TEST_TG_ID)
    sub = create_subscription(db_session, user_id=user.id, subscription_id=STRIPE_SUB_ID, order_id="old_order", payment_system="stripe")
    # "Состарим" подписку, чтобы было что продлевать
    sub.expires_at = datetime.utcnow() + timedelta(days=1)
    db_session.commit()
    
    response = client.post("/webhook/stripe", data=json.dumps(stripe_invoice_paid), content_type="application/json")

    assert response.status_code == 200
    db_session.refresh(sub)
    # Проверяем, что дата окончания сдвинулась примерно на 30 дней в будущее
    assert sub.expires_at > datetime.utcnow() + timedelta(days=28)
    mock_send_notification.assert_called_once()

@patch('payment_service.verify_stripe_webhook')
@patch('telegram_service.TelegramService.send_subscription_cancelled_notification', new_callable=MagicMock)
def test_stripe_webhook_subscription_deleted(mock_send_notification, mock_verify, client, db_session):
    """Тест [Stripe]: Отмена подписки."""
    from database import create_user, create_subscription, activate_subscription
    mock_verify.return_value = stripe_subscription_deleted

    user = create_user(db_session, telegram_id=TEST_TG_ID)
    sub = create_subscription(db_session, user_id=user.id, subscription_id=STRIPE_SUB_ID, order_id="ord_del", payment_system="stripe")
    activate_subscription(db_session, user_id=user.id, order_id="ord_del")

    response = client.post("/webhook/stripe", data=json.dumps(stripe_subscription_deleted), content_type="application/json")

    assert response.status_code == 200
    db_session.refresh(sub)
    assert sub.status == "cancelled"
    mock_send_notification.assert_called_once()

# === Тесты для PayPal ===

@patch('payment_service.verify_paypal_webhook', return_value=True)
@patch('telegram_service.TelegramService.send_payment_success_notification', new_callable=MagicMock)
def test_paypal_webhook_activated(mock_send_notification, mock_verify, client, db_session):
    """Тест [PayPal]: Успешная активация новой подписки."""
    from database import create_user, create_subscription, get_active_subscription
    
    user = create_user(db_session, telegram_id=TEST_TG_ID)
    create_subscription(db_session, user_id=user.id, order_id=PAYPAL_SUB_ID, payment_system="paypal")

    response = client.post("/webhook/paypal", data=json.dumps(paypal_activated), content_type="application/json")
    
    assert response.status_code == 200
    active_sub = get_active_subscription(db_session, user_id=user.id)
    assert active_sub is not None
    assert active_sub.status == "active"
    mock_send_notification.assert_called_once()

@patch('payment_service.verify_paypal_webhook', return_value=True)
@patch('telegram_service.TelegramService.send_subscription_cancelled_notification', new_callable=MagicMock)
def test_paypal_webhook_cancelled(mock_send_notification, mock_verify, client, db_session):
    """Тест [PayPal]: Отмена подписки."""
    from database import create_user, create_subscription, activate_subscription
    
    user = create_user(db_session, telegram_id=TEST_TG_ID)
    sub = create_subscription(db_session, user_id=user.id, subscription_id=PAYPAL_SUB_ID, order_id="ord_cancel", payment_system="paypal")
    activate_subscription(db_session, user_id=user.id, order_id="ord_cancel")

    response = client.post("/webhook/paypal", data=json.dumps(paypal_cancelled), content_type="application/json")

    assert response.status_code == 200
    db_session.refresh(sub)
    assert sub.status == "cancelled"
    mock_send_notification.assert_called_once()
