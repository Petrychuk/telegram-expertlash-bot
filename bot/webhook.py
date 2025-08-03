from flask import Flask, request, jsonify
from flask_cors import CORS
import stripe
import threading
import asyncio
import logging
from datetime import datetime

from  payment_config import STRIPE_WEBHOOK_SECRET, PAYPAL_WEBHOOK_SECRET, CLOSED_GROUP_LINK
from  payment_service import verify_stripe_webhook, verify_paypal_webhook
from  database import (
    get_db, get_subscription_by_id, activate_subscription, 
    cancel_subscription, get_user_by_telegram_id
)
from  telegram_service import TelegramService

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)  # Разрешаем CORS для всех доменов

# Инициализируем Telegram сервис
telegram_service = TelegramService()

@app.route('/webhook/stripe', methods=['POST'])
def stripe_webhook():
    """Обработка вебхуков от Stripe"""
    payload = request.get_data()
    sig_header = request.headers.get('stripe-signature')
    
    try:
        # Проверяем подпись вебхука
        event = verify_stripe_webhook(payload, sig_header)
        if not event:
            logger.error("Invalid Stripe webhook signature")
            return jsonify({'error': 'Invalid signature'}), 400
        
        logger.info(f"Received Stripe webhook: {event['type']}")
        
        # Обрабатываем различные типы событий
        if event['type'] == 'checkout.session.completed':
            # Успешная оплата подписки
            session = event['data']['object']
            handle_stripe_payment_success(session)
            
        elif event['type'] == 'customer.subscription.created':
            # Создана подписка
            subscription = event['data']['object']
            handle_stripe_subscription_created(subscription)
            
        elif event['type'] == 'customer.subscription.updated':
            # Обновлена подписка (например, изменен статус)
            subscription = event['data']['object']
            handle_stripe_subscription_updated(subscription)
            
        elif event['type'] == 'customer.subscription.deleted':
            # Отменена подписка
            subscription = event['data']['object']
            handle_stripe_subscription_cancelled(subscription)
            
        elif event['type'] == 'invoice.payment_succeeded':
            # Успешная оплата счета (авточардж)
            invoice = event['data']['object']
            handle_stripe_payment_succeeded(invoice)
            
        elif event['type'] == 'invoice.payment_failed':
            # Неуспешная оплата счета (авточардж)
            invoice = event['data']['object']
            handle_stripe_payment_failed(invoice)
            
        else:
            logger.info(f"Unhandled Stripe event type: {event['type']}")
        
        return jsonify({'status': 'success'}), 200
        
    except Exception as e:
        logger.error(f"Error processing Stripe webhook: {str(e)}")
        return jsonify({'error': 'Webhook processing failed'}), 500

@app.route('/webhook/paypal', methods=['POST'])
def paypal_webhook():
    """Обработка вебхуков от PayPal"""
    try:
        headers = request.headers
        body = request.get_data()
        
        # Проверяем подпись вебхука (упрощенная версия)
        if not verify_paypal_webhook(headers, body):
            logger.error("Invalid PayPal webhook signature")
            return jsonify({'error': 'Invalid signature'}), 400
        
        data = request.get_json()
        event_type = data.get('event_type')
        
        logger.info(f"Received PayPal webhook: {event_type}")
        
        # Обрабатываем различные типы событий
        if event_type == 'PAYMENT.SALE.COMPLETED':
            # Успешная оплата
            resource = data.get('resource', {})
            handle_paypal_payment_success(resource)
            
        elif event_type == 'BILLING.SUBSCRIPTION.CREATED':
            # Создана подписка
            resource = data.get('resource', {})
            handle_paypal_subscription_created(resource)
            
        elif event_type == 'BILLING.SUBSCRIPTION.CANCELLED':
            # Отменена подписка
            resource = data.get('resource', {})
            handle_paypal_subscription_cancelled(resource)
            
        elif event_type == 'BILLING.SUBSCRIPTION.PAYMENT.FAILED':
            # Неуспешная оплата подписки
            resource = data.get('resource', {})
            handle_paypal_payment_failed(resource)
            
        else:
            logger.info(f"Unhandled PayPal event type: {event_type}")
        
        return jsonify({'status': 'success'}), 200
        
    except Exception as e:
        logger.error(f"Error processing PayPal webhook: {str(e)}")
        return jsonify({'error': 'Webhook processing failed'}), 500

def handle_stripe_payment_success(session):
    """Обработка успешной оплаты Stripe"""
    try:
        session_id = session['id']
        customer_id = session.get('customer')
        telegram_id = session.get('metadata', {}).get('telegram_id')
        
        if not telegram_id:
            logger.error(f"No telegram_id in session metadata: {session_id}")
            return
        
        telegram_id = int(telegram_id)
        
        # Активируем подписку в БД
        db = next(get_db())
        try:
            subscription = activate_subscription(db, session_id)
            if subscription:
                logger.info(f"Activated subscription for user {telegram_id} with subscription_id {session_id}")
                print(f"[DEBUG] Activated subscription: {subscription}")
                
                # Отправляем уведомление пользователю — правильно запускаем async-функцию
                threading.Thread(target=lambda: asyncio.run(
                    telegram_service.send_payment_success_notification(telegram_id, subscription)
                )).start()
            else:
                logger.error(f"Subscription not found for session: {session_id}")
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Error handling Stripe payment success: {str(e)}")

def handle_stripe_subscription_created(subscription):
    """Обработка создания подписки Stripe"""
    logger.info(f"Stripe subscription created: {subscription['id']}")

def handle_stripe_subscription_updated(subscription):
    """Обработка обновления подписки Stripe"""
    logger.info(f"Stripe subscription updated: {subscription['id']}, status: {subscription['status']}")

def handle_stripe_subscription_cancelled(subscription):
    """Обработка отмены подписки Stripe"""
    try:
        subscription_id = subscription['id']
        customer_id = subscription.get('customer')
        
        # Отменяем подписку в БД
        db = next(get_db())
        try:
            cancelled_subscription = cancel_subscription(db, subscription_id)
            if cancelled_subscription:
                logger.info(f"Cancelled subscription: {subscription_id}")
                
                threading.Thread(target=lambda: asyncio.run(
                    telegram_service.send_subscription_cancelled_notification(cancelled_subscription.telegram_id)
                )).start()

            else:
                logger.error(f"Subscription not found for cancellation: {subscription_id}")
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Error handling Stripe subscription cancellation: {str(e)}")

def handle_stripe_payment_succeeded(invoice):
    """Обработка успешной оплаты счета (авточардж)"""
    try:
        subscription_id = invoice.get('subscription')
        customer_id = invoice.get('customer')
        
        logger.info(f"Stripe payment succeeded for subscription: {subscription_id}")
        
        # Продлеваем подписку (если нужно)
        db = next(get_db())
        try:
            subscription = get_subscription_by_id(db, subscription_id)
            if subscription:
                # Обновляем дату окончания подписки
                from datetime import timedelta
                subscription.expires_at = datetime.utcnow() + timedelta(days=30)
                subscription.status = "active"
                subscription.has_group_access = True
                db.commit()
                
                threading.Thread(target=lambda: asyncio.run(
                    telegram_service.send_subscription_renewed_notification(subscription.telegram_id, subscription)
                )).start()

        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Error handling Stripe payment succeeded: {str(e)}")

def handle_stripe_payment_failed(invoice):
    """Обработка неуспешной оплаты счета (авточардж)"""
    try:
        subscription_id = invoice.get('subscription')
        customer_id = invoice.get('customer')
        
        logger.info(f"Stripe payment failed for subscription: {subscription_id}")
        
        # Уведомляем пользователя о проблеме с оплатой
        db = next(get_db())
        try:
            subscription = get_subscription_by_id(db, subscription_id)
            if subscription:
                threading.Thread(target=lambda: asyncio.run(
                telegram_service.send_payment_failed_notification(subscription.telegram_id)
            )).start()
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Error handling Stripe payment failed: {str(e)}")

def handle_paypal_payment_success(resource):
    """Обработка успешной оплаты PayPal"""
    try:
        # PayPal структура данных отличается от Stripe
        order_id = resource.get('parent_payment')
        custom_id = resource.get('custom')  # Здесь должен быть telegram_id
        
        if custom_id:
            telegram_id = int(custom_id)
            
            # Активируем подписку в БД
            db = next(get_db())
            try:
                subscription = activate_subscription(db, order_id)
                if subscription:
                    logger.info(f"Activated PayPal subscription for user {telegram_id}")
                    
                    # Отправляем уведомление пользователю
                    asyncio.create_task(telegram_service.send_payment_success_notification(
                        telegram_id, subscription
                    ))
            finally:
                db.close()
                
    except Exception as e:
        logger.error(f"Error handling PayPal payment success: {str(e)}")

def handle_paypal_subscription_created(resource):
    """Обработка создания подписки PayPal"""
    logger.info(f"PayPal subscription created: {resource.get('id')}")

def handle_paypal_subscription_cancelled(resource):
    """Обработка отмены подписки PayPal"""
    try:
        subscription_id = resource.get('id')
        
        # Отменяем подписку в БД
        db = next(get_db())
        try:
            cancelled_subscription = cancel_subscription(db, subscription_id)
            if cancelled_subscription:
                logger.info(f"Cancelled PayPal subscription: {subscription_id}")
                
                # Отправляем уведомление пользователю
                asyncio.create_task(telegram_service.send_subscription_cancelled_notification(
                    cancelled_subscription.telegram_id
                ))
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Error handling PayPal subscription cancellation: {str(e)}")

def handle_paypal_payment_failed(resource):
    """Обработка неуспешной оплаты PayPal"""
    try:
        subscription_id = resource.get('billing_agreement_id')
        
        logger.info(f"PayPal payment failed for subscription: {subscription_id}")
        
        # Уведомляем пользователя о проблеме с оплатой
        db = next(get_db())
        try:
            subscription = get_subscription_by_id(db, subscription_id)
            if subscription:
                asyncio.create_task(telegram_service.send_payment_failed_notification(
                    subscription.telegram_id
                ))
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Error handling PayPal payment failed: {str(e)}")

@app.route('/health', methods=['GET'])
def health_check():
    """Проверка работоспособности сервера"""
    return jsonify({'status': 'healthy', 'timestamp': datetime.utcnow().isoformat()}), 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
