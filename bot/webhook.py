import os

from flask import Flask, request, jsonify, redirect
from flask_cors import CORS
import stripe
import threading
import asyncio
import logging
from datetime import datetime, timedelta
from functools import wraps

from payment_config import STRIPE_WEBHOOK_SECRET, PAYPAL_WEBHOOK_ID, CLOSED_GROUP_LINK
from payment_service import verify_stripe_webhook, verify_paypal_webhook, PayPalService, StripeService
from database import (
    get_db, get_subscription_by_id, activate_subscription,
    cancel_subscription, get_user_by_telegram_id
)
from telegram_service import TelegramService

app = Flask(__name__)
CORS(app)
telegram_service = TelegramService()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# === Утилиты ===
def with_db_session(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        db = next(get_db())
        try:
            result = fn(db, *args, **kwargs)
            db.commit()
            return result
        except Exception as e:
            db.rollback()
            logger.error(f"DB error in {fn.__name__}: {e}")
            raise
        finally:
            db.close()
    return wrapper

def run_async_in_thread(coro):
    threading.Thread(target=lambda: asyncio.run(coro)).start()

# === Webhooks ===
@app.route('/webhook/stripe', methods=['POST'])
def stripe_webhook():
    payload = request.get_data()
    sig_header = request.headers.get('stripe-signature')
    event = StripeService.verify_webhook(payload, sig_header)
    try:
        event = verify_stripe_webhook(payload, sig_header)
        if not event:
            return jsonify({'error': 'Invalid signature'}), 400

        logger.info(f"Stripe webhook received: {event['type']}")
        data = event['data']['object']
        handlers = {
            'checkout.session.completed': handle_stripe_payment_success,
            'customer.subscription.created': handle_stripe_subscription_created,
            'customer.subscription.updated': handle_stripe_subscription_updated,
            'customer.subscription.deleted': handle_stripe_subscription_cancelled,
            'invoice.payment_succeeded': handle_stripe_payment_succeeded,
            'invoice.payment_failed': handle_stripe_payment_failed,
        }

        handler = handlers.get(event['type'])
        if handler:
            handler(data)
        else:
            logger.info(f"Unhandled Stripe event type: {event['type']}")

        return jsonify({'status': 'success'}), 200

    except Exception as e:
        logger.error(f"Stripe webhook error: {e}")
        return jsonify({'error': 'Webhook processing failed'}), 500

from database import get_db, activate_subscription, cancel_subscription

@app.route('/webhook/paypal', methods=['POST'])
def paypal_webhook():
    headers = request.headers
    body = request.get_data(as_text=True)

    if not verify_paypal_webhook(headers, body):
        logger.warning("PayPal webhook verification failed")
        return jsonify({'error': 'Invalid signature'}), 400
    
    data = request.get_json()
    PayPalService.verify_webhook(data)
    event_type = data.get('event_type')
    resource = data.get('resource', {}) or {}
    
    logger.info(f"PayPal webhook: {event_type}")

    db = next(get_db())
    try:
        # PayPal присылает id подписки в resource.id (надежный ключ)
        paypal_subscription_id = resource.get("id")
        # telegram_id мы обычно передаём в custom_id при создании/оплате
        raw_tid = resource.get("custom_id") or resource.get("custom")
        try:
            telegram_id = int(raw_tid) if raw_tid is not None else None
        except (TypeError, ValueError):
            telegram_id = None

        if event_type == "BILLING.SUBSCRIPTION.ACTIVATED":
            sub = activate_subscription(db, order_id=paypal_subscription_id, telegram_id=telegram_id)

            if sub and sub.status == "active":
                run_async_in_thread(
                    telegram_service.send_payment_success_notification(sub.telegram_id, sub)
                )
                logger.info(f"PayPal subscription activated: {sub.subscription_id or sub.order_id} for telegram_id={sub.telegram_id}")
            else:
                logger.error(f"Activation failed or not active for paypal_id={paypal_subscription_id}, tid={telegram_id}")

        elif event_type in ("BILLING.SUBSCRIPTION.CANCELLED", "BILLING.SUBSCRIPTION.EXPIRED"):
            logger.info(f"Подписка отменена/истекла: paypal_id={paypal_subscription_id}")
            cancel_subscription(db, subscription_id=paypal_subscription_id)

        elif event_type == "BILLING.SUBSCRIPTION.PAYMENT.FAILED":
            logger.warning(f"Проблема с оплатой подписки: paypal_id={paypal_subscription_id}")
        # Остальные события логируем по необходимости

    finally:
        db.close()

    return jsonify({'status': 'ok'}), 200

# === Stripe Handlers ===
@with_db_session
def handle_stripe_payment_success(db, session):
    """Обработка успешной оплаты Stripe"""
    telegram_id = session.get('metadata', {}).get('telegram_id')
    if not telegram_id:
        logger.error(f"No telegram_id in session: {session['id']}")
        return

    telegram_id = int(telegram_id)
    subscription_id = session.get('subscription')
    if not subscription_id:
       logger.error(f"No subscription id in session: {session['id']}")
       return

    subscription = activate_subscription(db, subscription_id)
    if subscription:
        logger.info(f"Stripe subscription activated: {subscription_id} for telegram_id {telegram_id}")
    else:
        logger.error(f"Failed to activate Stripe subscription: {subscription_id}")
        
@with_db_session
def handle_stripe_payment_succeeded(db, invoice):
    logger.info(f"handle_stripe_payment_succeeded called with invoice data: {invoice}")
    subscription_id = invoice.get('subscription')
    if not subscription_id:
        logger.warning("No subscription ID found in invoice, skipping subscription activation")
        return

    sub = get_subscription_by_id(db, subscription_id)
    if sub:
        sub.expires_at = datetime.utcnow() + timedelta(days=30)
        sub.status = "active"
        sub.has_group_access = True
        logger.info(f"Subscription {subscription_id} activated")
        run_async_in_thread(telegram_service.send_subscription_renewed_notification(sub.telegram_id, sub))
    else:
        logger.error(f"Subscription not found for id: {subscription_id}")

@with_db_session
def handle_stripe_subscription_created(db, subscription):
    logger.info(f"Stripe subscription created: {subscription['id']}")
    # реализация при необходимости

@with_db_session
def handle_stripe_subscription_updated(db, subscription):
    sub = get_subscription_by_id(db, subscription['id'])
    if sub:
        sub.status = subscription['status']
        logger.info(f"Subscription updated: {subscription['id']} -> {subscription['status']}")

@with_db_session
def handle_stripe_subscription_cancelled(db, subscription):
    sub = get_subscription_by_id(db, subscription['id'])
    if sub:
        sub.status = "canceled"
        sub.has_group_access = False
        logger.info(f"Subscription {subscription['id']} canceled — доступ закрыт")
        run_async_in_thread(telegram_service.send_subscription_cancelled_notification(sub.telegram_id))
    else:
        logger.error(f"Subscription not found for cancellation id: {subscription['id']}")

@with_db_session
def handle_stripe_payment_failed(db, invoice):
    subscription_id = invoice.get('subscription')
    if not subscription_id:
        logger.warning("No subscription ID found in failed invoice")
        return
    
    sub = get_subscription_by_id(db, subscription_id)
    if sub:
        # Можно обновить статус, например:
        sub.status = "past_due"
        sub.has_group_access = False
        logger.info(f"Subscription {subscription_id} payment failed — доступ закрыт")
        run_async_in_thread(telegram_service.send_payment_failed_notification(sub.telegram_id))
    else:
        logger.error(f"Subscription not found for failed invoice id: {subscription_id}")

# === PayPal Handlers ===
@with_db_session
def handle_paypal_payment_success(db, resource):
    logger.info(f"PayPal resource received: {resource}")

    telegram_id = None
    subscription_id = None

    # Попытка получить telegram_id из custom/custom_id
    if 'custom' in resource:
        telegram_id = resource.get('custom')
    elif 'custom_id' in resource:
        telegram_id = resource.get('custom_id')
    elif 'supplementary_data' in resource and 'custom' in resource['supplementary_data']:
        telegram_id = resource['supplementary_data']['custom']

    try:
        telegram_id = int(telegram_id)
    except (TypeError, ValueError):
        logger.error(f"Invalid or missing telegram_id: {telegram_id}")
        return

    # Попытка получить subscription ID
    subscription_id = (
        resource.get('billing_agreement_id')
        or resource.get('subscription_id')
        or resource.get('id')
    )
    logger.info(f"Extracted subscription_id: {subscription_id}")
    if not subscription_id:
        logger.error("No valid subscription ID found in PayPal resource")
        return

    subscription = activate_subscription(db, subscription_id)
    if subscription and subscription.status == "active":
        logger.info(f"Subscription activated: {subscription}")
        run_async_in_thread(
             telegram_service.send_payment_success_notification(telegram_id, subscription)
        )
        logger.info(f"Payment success notification sent for telegram_id {telegram_id}")
    else:
        logger.error(f"Subscription not found or could not be activated: {subscription_id}")

@with_db_session
def handle_paypal_subscription_created(db, resource):
    logger.info(f"PayPal subscription created: {resource.get('id')}")
    # реализация при необходимости

@with_db_session
def handle_paypal_checkout_order_approved(db, resource):
    try:
        telegram_id = int(resource.get('custom'))
    except (TypeError, ValueError):
        logger.error("Invalid or missing telegram_id in CHECKOUT.ORDER.APPROVED")
        return

    subscription_id = resource.get('id')
    if not subscription_id:
        logger.error("Missing subscription_id in CHECKOUT.ORDER.APPROVED")
        return

    subscription = activate_subscription(db, subscription_id)
    if subscription and subscription.status == "active":
        run_async_in_thread(
            telegram_service.send_payment_success_notification(telegram_id, subscription)
        )
        logger.info(f"[CHECKOUT.ORDER.APPROVED] Subscription activated for user {telegram_id}")
    else:
        logger.error(f"[CHECKOUT.ORDER.APPROVED] Could not activate subscription: {subscription_id}")

@with_db_session
def handle_paypal_capture_completed(db, resource):
    """Обработка успешного завершения захвата платежа PayPal"""
    order_id = resource.get('supplementary_data', {}).get('related_ids', {}).get('order_id')
    custom_id = resource.get('custom_id')

    if not order_id or not custom_id:
        logger.error("Missing order_id or custom_id in PAYPAL_CAPTURE_COMPLETED webhook")
        return

    try:
        telegram_id = int(custom_id)
    except Exception:
        logger.error(f"Invalid telegram_id: {custom_id}")
        return

    subscription = activate_subscription(db, order_id)
    if subscription and subscription.status == "active":
        logger.info(f"PayPal subscription activated: {order_id} for telegram_id {telegram_id}")
        run_async_in_thread(
            telegram_service.send_payment_success_notification(telegram_id, subscription)
        )
    else:
        logger.error(f"Failed to activate PayPal subscription: {order_id}")
        
@with_db_session
def handle_paypal_subscription_cancelled(db, resource):
    sub = cancel_subscription(db, resource.get('id'))
    if sub:
        run_async_in_thread(telegram_service.send_subscription_cancelled_notification(sub.telegram_id))

@with_db_session
def handle_paypal_payment_failed(db, resource):
    sub = get_subscription_by_id(db, resource.get('billing_agreement_id'))
    if sub:
        run_async_in_thread(telegram_service.send_payment_failed_notification(sub.telegram_id))

# === Вспомогательные маршруты ===
@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({'status': 'healthy', 'timestamp': datetime.utcnow().isoformat()}), 200

@app.route('/stripe/return', methods=['GET'])
@with_db_session
def stripe_return(db):
    session_id = request.args.get('session_id')
    if not session_id:
        return "<h2>Ошибка: session_id отсутствует</h2>", 400

    # Тут нужно получить подписку по session_id
    subscription = get_subscription_by_id(db, session_id)
    if not subscription:
        # Возможно, session_id это id checkout сессии, тогда придется искать по другому
        return "<h2>Подписка не найдена</h2>", 404

    # Активируем подписку (если еще не активирована)
    if subscription.status != "active":
        subscription.status = "active"
        subscription.activated_at = datetime.utcnow()
        subscription.expires_at = subscription.activated_at + timedelta(days=30)
        subscription.has_group_access = True
        db.commit()

    # Отправка уведомления в Telegram (асинхронно)
    run_async_in_thread(
        telegram_service.send_payment_success_notification(subscription.telegram_id, subscription)
    )

    # Редирект на закрытую группу
    return redirect(CLOSED_GROUP_LINK)

@app.route('/stripe/cancel', methods=['GET'])
def stripe_cancel():
    return "<h2>❌ Stripe: Подписка была отменена.</h2>", 200

@app.route('/paypal/return', methods=['GET'])
def paypal_return():
    # PayPal на return обычно кладёт token = id подписки (или order token)
    subscription_id = request.args.get('token')
    logger.info(f"PayPal return received: subscription_id={subscription_id}")

    db = next(get_db())
    try:
        sub = get_subscription_by_id(db, subscription_id) or get_subscription_by_id(db, str(subscription_id))
        if sub and sub.status == "active":
            return redirect(CLOSED_GROUP_LINK)

        # Если подписка не активна, НИКАКИХ ссылок
        return "<h2>Оплата получена. Доступ будет выдан после подтверждения — проверьте сообщение в Telegram.</h2>", 200
    finally:
        db.close()

@app.route('/paypal/cancel', methods=['GET'])
def paypal_cancel():
    return "<h2>❌ PayPal: Вы отменили оплату.</h2>", 200

@app.route("/")
def index():
    return "Bot and webhook are running!"

