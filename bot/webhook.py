import os

from flask import Flask, request, jsonify, redirect
from flask_cors import CORS
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
    threading.Thread(target=lambda: asyncio.run(coro), daemon=True).start()

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
    headers = request.headers
    body = request.get_data(as_text=True)

    if not verify_paypal_webhook(headers, body):
        logger.warning("PayPal webhook verification failed")
        return jsonify({'error': 'Invalid signature'}), 400

    data = request.get_json(silent=True) or {}
    event_type = data.get('event_type')
    resource = data.get('resource', {}) or {}

    logger.info(f"PayPal webhook: {event_type}")

    db = next(get_db())
    try:
        paypal_subscription_id = resource.get("id")
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
                logger.info(f"PayPal subscription activated: {paypal_subscription_id} for telegram_id={sub.telegram_id}")
            else:
                logger.error(f"Activation failed for paypal_id={paypal_subscription_id}, tid={telegram_id}")

        elif event_type in ("BILLING.SUBSCRIPTION.CANCELLED", "BILLING.SUBSCRIPTION.EXPIRED"):
            logger.info(f"PayPal subscription cancelled/expired: paypal_id={paypal_subscription_id}")
            cancel_subscription(db, subscription_id=paypal_subscription_id)

        elif event_type == "BILLING.SUBSCRIPTION.PAYMENT.FAILED":
            logger.warning(f"PayPal payment failed: paypal_id={paypal_subscription_id}")

    finally:
        db.close()

    return jsonify({'status': 'ok'}), 200

# === Stripe Handlers ===
@with_db_session
def handle_stripe_payment_success(db, session):
    """
    checkout.session.completed
    В session:
      - id: cs_...
      - subscription: sub_...
      - metadata.telegram_id
    """
    logger.info(f"handle_stripe_payment_success: session_id={session.get('id')}, subscription={session.get('subscription')}")

    tg = session.get('metadata', {}).get('telegram_id')
    try:
        telegram_id = int(tg) if tg is not None else None
    except (TypeError, ValueError):
        telegram_id = None

    session_id = session.get('id')
    real_sub_id = session.get('subscription')
    if not real_sub_id:
        logger.error(f"No real subscription id in session: {session_id}")
        return

    # 1) пробуем найти по real subscription id
    sub = get_subscription_by_id(db, real_sub_id)

    # 2) если не нашли — пробуем по временному session_id (мы сохраняли его в момент создания)
    if not sub and session_id:
        sub = get_subscription_by_id(db, session_id)
        if sub:
            # сводим идентификаторы: теперь у записи должен быть реальный subscription_id
            try:
                sub.subscription_id = real_sub_id
            except Exception:
                pass  # если модели нет такого поля — просто активируем по функции ниже

    # 3) активируем
    activated = activate_subscription(db, real_sub_id, telegram_id=telegram_id)
    if activated and activated.status == "active":
        logger.info(f"Stripe subscription activated: {real_sub_id} (user {activated.telegram_id})")
        run_async_in_thread(
            telegram_service.send_payment_success_notification(activated.telegram_id, activated)
        )
    else:
        logger.error(f"Failed to activate Stripe subscription: {real_sub_id}")

@with_db_session
def handle_stripe_payment_succeeded(db, invoice):
    """
    invoice.payment_succeeded — продление/первичная активация на всякий случай
    """
    subscription_id = invoice.get('subscription')
    if not subscription_id:
        logger.warning("No subscription ID in invoice")
        return

    sub = get_subscription_by_id(db, subscription_id)
    if sub:
        sub.expires_at = datetime.utcnow() + timedelta(days=30)
        sub.status = "active"
        sub.has_group_access = True
        logger.info(f"Subscription {subscription_id} extended/activated to {sub.expires_at}")
        run_async_in_thread(
            telegram_service.send_subscription_renewed_notification(sub.telegram_id, sub)
        )
    else:
        logger.error(f"Subscription not found for id: {subscription_id}")

@with_db_session
def handle_stripe_subscription_created(db, subscription):
    logger.info(f"Stripe subscription created: {subscription.get('id')}")

@with_db_session
def handle_stripe_subscription_updated(db, subscription):
    sub = get_subscription_by_id(db, subscription.get('id'))
    if sub:
        sub.status = subscription.get('status')
        logger.info(f"Subscription updated: {subscription.get('id')} -> {subscription.get('status')}")

@with_db_session
def handle_stripe_subscription_cancelled(db, subscription):
    sub = get_subscription_by_id(db, subscription.get('id'))
    if sub:
        sub.status = "canceled"
        sub.has_group_access = False
        logger.info(f"Subscription {subscription.get('id')} canceled — access revoked")
        run_async_in_thread(telegram_service.send_subscription_cancelled_notification(sub.telegram_id))
    else:
        logger.error(f"Subscription not found for cancellation id: {subscription.get('id')}")

@with_db_session
def handle_stripe_payment_failed(db, invoice):
    subscription_id = invoice.get('subscription')
    if not subscription_id:
        logger.warning("No subscription ID in failed invoice")
        return

    sub = get_subscription_by_id(db, subscription_id)
    if sub:
        sub.status = "past_due"
        sub.has_group_access = False
        logger.info(f"Subscription {subscription_id} payment failed — access revoked")
        run_async_in_thread(telegram_service.send_payment_failed_notification(sub.telegram_id))
    else:
        logger.error(f"Subscription not found for failed invoice id: {subscription_id}")

# === PayPal extra handlers (по необходимости) ===
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
    # ВАЖНО: активацию выполняют вебхуки. Этот роут — только для UX.
    return "<h2>Grazie! Il pagamento è stato ricevuto. Controlla i messaggi su Telegram per l'accesso al gruppo.</h2>", 200

@app.route('/stripe/cancel', methods=['GET'])
def stripe_cancel():
    return "<h2>❌ Stripe: hai annullato il pagamento.</h2>", 200

@app.route('/paypal/return', methods=['GET'])
def paypal_return():
    # PayPal кладёт token=subscription_id/order token; активацию делает вебхук
    return "<h2>Grazie! Il pagamento è stato ricevuto. L'accesso verrà rilasciato dopo la conferma. Controlla Telegram.</h2>", 200

@app.route('/paypal/cancel', methods=['GET'])
def paypal_cancel():
    return "<h2>❌ PayPal: hai annullato il pagamento.</h2>", 200

@app.route("/")
def index():
    return "Bot and webhook are running!"
