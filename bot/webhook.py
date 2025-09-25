#webhook.py
import os
import stripe
from datetime import datetime
from flask import Flask, request, jsonify
from auth_telegram import bp as tg_bp
from flask_cors import CORS
import threading
import asyncio
import logging

# --- Правильные импорты ---
from payment_service import verify_stripe_webhook, verify_paypal_webhook
from database import get_db, activate_subscription, cancel_subscription
from telegram_service import TelegramService

# --- Инициализация ---
app = Flask(__name__)
CORS(app)
app.config["BOT_TOKEN"] = os.getenv("BOT_TOKEN")
app.config["JWT_SECRET"] = os.getenv("JWT_SECRET", "devsecret")
app.register_blueprint(tg_bp)
telegram_service = TelegramService()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def run_async_in_thread(coro):
    """Запускает асинхронную задачу в отдельном потоке."""
    threading.Thread(target=lambda: asyncio.run(coro), daemon=True).start()

# === Вебхук Stripe: ===
@app.route('/webhook/stripe', methods=['POST'])
def stripe_webhook():
    payload = request.get_data()
    sig_header = request.headers.get('stripe-signature')
    try:
        event = verify_stripe_webhook(payload, sig_header)
        if not event:
            logger.warning("Stripe webhook verification failed.")
            return jsonify({'error': 'Invalid signature'}), 400

        logger.info(f"Stripe webhook received: {event['type']}")
        data = event['data']['object']

        # 1. ГЛАВНОЕ СОБЫТИЕ: Активация подписки после успешной оплаты
        if event['type'] == 'checkout.session.completed':
            session = data
            user_id = session.get('metadata', {}).get('user_id')
            order_id = session.get('id') 

            if not user_id:
                logger.error(f"Stripe 'checkout.session.completed' without user_id in metadata. Order ID: {order_id}")
                return jsonify({'error': 'Missing user_id'}), 400

            db = next(get_db())
            try:
                # Вызываем нашу надежную функцию активации
                activated_sub = activate_subscription(
                    db, user_id=int(user_id), order_id=order_id,
                    amount=session.get('amount_total', 0) / 100.0, currency=session.get('currency')
                )
                if activated_sub:
                    logger.info(f"Stripe subscription activated for user_id={user_id} via order_id={order_id}")
                    run_async_in_thread(telegram_service.send_payment_success_notification(activated_sub.telegram_id, activated_sub))
                else:
                    logger.error(f"Failed to activate Stripe subscription for user_id={user_id}, order_id={order_id}")
            finally:
                db.close()

        # 2. СОБЫТИЕ: Отмена подписки (например, пользователем в личном кабинете Stripe)
        elif event['type'] == 'customer.subscription.deleted':
            subscription_id = data.get('id')
            if subscription_id:
                db = next(get_db())
                try:
                    sub = cancel_subscription(db, subscription_id=subscription_id)
                    if sub:
                        logger.info(f"Stripe subscription cancelled: {subscription_id}")
                        run_async_in_thread(telegram_service.send_subscription_cancelled_notification(sub.telegram_id))
                finally:
                    db.close()
        
        return jsonify({'status': 'success'}), 200

    except Exception as e:
        logger.error(f"Stripe webhook error: {e}", exc_info=True)
        return jsonify({'error': 'Webhook processing failed'}), 500

# === Вебхук PayPal:===
@app.route('/webhook/paypal', methods=['POST'])
def paypal_webhook():
    if not verify_paypal_webhook(request.headers, request.get_data(as_text=True)):
        logger.warning("PayPal webhook verification failed")
        return jsonify({'error': 'Invalid signature'}), 400

    data = request.get_json(silent=True) or {}
    event_type = data.get('event_type')
    resource = data.get('resource', {}) or {}
    logger.info(f"PayPal webhook received: {event_type}")

    # 1. ГЛАВНОЕ СОБЫТИЕ: Активация подписки
    if event_type == "BILLING.SUBSCRIPTION.ACTIVATED":
        paypal_sub_id = resource.get("id")
        user_id = resource.get("custom_id") #

        if not user_id:
            logger.error(f"PayPal 'ACTIVATED' without user_id in custom_id. PayPal Sub ID: {paypal_sub_id}")
            return jsonify({'error': 'Missing user_id'}), 400

        db = next(get_db())
        try:
            # Вызываем нашу надежную функцию активации
            activated_sub = activate_subscription(db, user_id=int(user_id), order_id=paypal_sub_id)
            if activated_sub:
                logger.info(f"PayPal subscription activated for user_id={user_id} via sub_id={paypal_sub_id}")
                run_async_in_thread(telegram_service.send_payment_success_notification(activated_sub.telegram_id, activated_sub))
            else:
                logger.error(f"Failed to activate PayPal subscription for user_id={user_id}, sub_id={paypal_sub_id}")
        finally:
            db.close()

    # 2. СОБЫТИЕ: Отмена подписки
    elif event_type in ("BILLING.SUBSCRIPTION.CANCELLED", "BILLING.SUBSCRIPTION.EXPIRED"):
        paypal_sub_id = resource.get("id")
        if paypal_sub_id:
            db = next(get_db())
            try:
                sub = cancel_subscription(db, subscription_id=paypal_sub_id)
                if sub:
                    logger.info(f"PayPal subscription cancelled/expired: {paypal_sub_id}")
                    run_async_in_thread(telegram_service.send_subscription_cancelled_notification(sub.telegram_id))
            finally:
                db.close()

    return jsonify({'status': 'ok'}), 200

# === Вспомогательные маршруты ===
@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({'status': 'healthy', 'timestamp': datetime.utcnow().isoformat()}), 200

@app.route('/stripe/return', methods=['GET'])
def stripe_return():
    # Итальянский: "Grazie! Il pagamento è stato ricevuto. Controlla i messaggi su Telegram per l'accesso al gruppo."
    # Русский: "Спасибо! Платеж получен. Проверьте сообщения в Telegram для получения доступа к группе."
    return "<h2>Спасибо! Платеж получен. Проверьте сообщения в Telegram для получения доступа к группе.</h2>", 200

@app.route('/stripe/cancel', methods=['GET'])
def stripe_cancel():
    # Итальянский: "❌ Stripe: hai annullato il pagamento."
    # Русский: "❌ Stripe: вы отменили платеж."
    return "<h2>❌ Stripe: вы отменили платеж.</h2>", 200

@app.route('/paypal/return', methods=['GET'])
def paypal_return():
    # Итальянский: "Grazie! Il pagamento è stato ricevuto. L'accesso verrà rilasciato dopo la conferma. Controlla Telegram."
    # Русский: "Спасибо! Платеж получен. Доступ будет предоставлен после подтверждения. Проверьте Telegram."
    return "<h2>Спасибо! Платеж получен. Доступ будет предоставлен после подтверждения. Проверьте Telegram.</h2>", 200

@app.route('/paypal/cancel', methods=['GET'])
def paypal_cancel():
    # Итальянский: "❌ PayPal: hai annullato il pagamento."
    # Русский: "❌ PayPal: вы отменили платеж."
    return "<h2>❌ PayPal: вы отменили платеж.</h2>", 200

@app.route("/")
def index():
    return "Bot and webhook are running!"
