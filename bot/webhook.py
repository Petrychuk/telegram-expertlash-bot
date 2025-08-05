from flask import Flask, request, jsonify
from flask_cors import CORS
import stripe
import threading
import asyncio
import logging
from datetime import datetime, timedelta
from functools import wraps

from payment_config import STRIPE_WEBHOOK_SECRET, PAYPAL_WEBHOOK_ID, CLOSED_GROUP_LINK
from payment_service import verify_stripe_webhook, verify_paypal_webhook
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

@app.route('/webhook/paypal', methods=['POST'])
def paypal_webhook():
    try:
        headers = request.headers
        body = request.get_data('utf-8')

        if not verify_paypal_webhook(headers, body):
            return jsonify({'error': 'Invalid signature'}), 400

        data = request.get_json()
        event_type = data.get('event_type')
        resource = data.get('resource', {})

        logger.info(f"PayPal webhook received: {event_type}")

        handlers = {
            'PAYMENT.SALE.COMPLETED': handle_paypal_payment_success,
            'BILLING.SUBSCRIPTION.CREATED': handle_paypal_subscription_created,
            'BILLING.SUBSCRIPTION.CANCELLED': handle_paypal_subscription_cancelled,
            'BILLING.SUBSCRIPTION.PAYMENT.FAILED': handle_paypal_payment_failed,
        }

        handler = handlers.get(event_type)
        if handler:
            handler(resource)
        else:
            logger.info(f"Unhandled PayPal event type: {event_type}")

        return jsonify({'status': 'success'}), 200

    except Exception as e:
        logger.error(f"PayPal webhook error: {e}")
        return jsonify({'error': 'Webhook processing failed'}), 500

# === Stripe Handlers ===
@with_db_session
def handle_stripe_payment_success(db, session):
    telegram_id = session.get('metadata', {}).get('telegram_id')
    if not telegram_id:
        logger.error(f"No telegram_id in session: {session['id']}")
        return

    telegram_id = int(telegram_id)
    subscription = activate_subscription(db, session['id'])
    if subscription:
        run_async_in_thread(telegram_service.send_payment_success_notification(telegram_id, subscription))

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
    sub = cancel_subscription(db, subscription['id'])
    if sub:
        run_async_in_thread(telegram_service.send_subscription_cancelled_notification(sub.telegram_id))

@with_db_session
def handle_stripe_payment_succeeded(db, invoice):
    sub = get_subscription_by_id(db, invoice.get('subscription'))
    if sub:
        sub.expires_at = datetime.utcnow() + timedelta(days=30)
        sub.status = "active"
        sub.has_group_access = True
        run_async_in_thread(telegram_service.send_subscription_renewed_notification(sub.telegram_id, sub))

@with_db_session
def handle_stripe_payment_failed(db, invoice):
    sub = get_subscription_by_id(db, invoice.get('subscription'))
    if sub:
        run_async_in_thread(telegram_service.send_payment_failed_notification(sub.telegram_id))

# === PayPal Handlers ===
@with_db_session
def handle_paypal_payment_success(db, resource):
    telegram_id = int(resource.get('custom'))
    order_id = resource.get('parent_payment')
    subscription = activate_subscription(db, order_id)
    if subscription:
        run_async_in_thread(telegram_service.send_payment_success_notification(telegram_id, subscription))

@with_db_session
def handle_paypal_subscription_created(db, resource):
    logger.info(f"PayPal subscription created: {resource.get('id')}")
    # реализация при необходимости

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
def stripe_return():
    return "<h2>✅ Stripe: Подписка успешно оформлена.</h2>", 200

@app.route('/stripe/cancel', methods=['GET'])
def stripe_cancel():
    return "<h2>❌ Stripe: Подписка была отменена.</h2>", 200

@app.route('/paypal/return', methods=['GET'])
def paypal_return():
    return "<h2>✅ PayPal: Оплата завершена успешно.</h2>", 200

@app.route('/paypal/cancel', methods=['GET'])
def paypal_cancel():
    return "<h2>❌ PayPal: Вы отменили оплату.</h2>", 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
