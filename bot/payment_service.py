import stripe
import json
import logging
import requests
from requests.auth import HTTPBasicAuth
from paypalcheckoutsdk.core import PayPalHttpClient, SandboxEnvironment
from payment_config import *

from database import create_subscription, activate_subscription, cancel_subscription, get_user_by_telegram_id

# Логгер
logger = logging.getLogger(__name__)

# Настройка Stripe
stripe.api_key = STRIPE_SECRET_KEY

# PayPal API базовый URL (песочница)
PAYPAL_API_BASE = "https://api.sandbox.paypal.com"

def get_paypal_access_token():
    """Получить OAuth2 токен для PayPal API"""
    url = PAYPAL_API_BASE + "/v1/oauth2/token"
    headers = {
        "Accept": "application/json",
        "Accept-Language": "en_US"
    }
    data = {
        "grant_type": "client_credentials"
    }
    response = requests.post(url, headers=headers, data=data, auth=HTTPBasicAuth(PAYPAL_CLIENT_ID, PAYPAL_CLIENT_SECRET))
    response.raise_for_status()
    token = response.json()['access_token']
    return token

class StripeService:
    @staticmethod
    def create_subscription_session(telegram_id: int, user_email: str = None):
        """Создание сессии подписки в Stripe"""
        try:
            customer = stripe.Customer.create(
                email=user_email,
                metadata={'telegram_id': str(telegram_id)}
            )
            try:
                product = stripe.Product.retrieve('lash_course_subscription')
            except stripe.error.InvalidRequestError:
                product = stripe.Product.create(
                    name='Курс "Ресницы от нуля до эксперта"',
                    description='Месячная подписка на курс по наращиванию ресниц'
                )
            try:
                price = stripe.Price.retrieve('price_1Rs2wB6S8Oc0JZWfqIIhtXze')
            except stripe.error.InvalidRequestError:
                price = stripe.Price.create(
                    product=product.id,
                    unit_amount=int(SUBSCRIPTION_PRICE * 100),
                    currency='eur',
                    recurring={'interval': 'month'}
                )
            session = stripe.checkout.Session.create(
                customer=customer.id,
                payment_method_types=['card'],
                line_items=[{'price': price.id, 'quantity': 1}],
                mode='subscription',
                success_url=STRIPE_RETURN_URL + '?session_id={CHECKOUT_SESSION_ID}',
                cancel_url=STRIPE_CANCEL_URL,
                metadata={'telegram_id': str(telegram_id)}
            )
            return {'success': True, 'session_id': session.id, 'url': session.url, 'customer_id': customer.id}
        except Exception as e:
            return {'success': False, 'error': str(e)}

    @staticmethod
    def get_subscription_status(subscription_id: str):
        try:
            subscription = stripe.Subscription.retrieve(subscription_id)
            return {
                'success': True,
                'status': subscription.status,
                'current_period_end': subscription.current_period_end,
                'customer_id': subscription.customer
            }
        except Exception as e:
            return {'success': False, 'error': str(e)}

    @staticmethod
    def cancel_subscription(subscription_id: str):
        try:
            subscription = stripe.Subscription.modify(
                subscription_id,
                cancel_at_period_end=True
            )
            return {
                'success': True,
                'status': subscription.status,
                'cancel_at_period_end': subscription.cancel_at_period_end
            }
        except Exception as e:
            return {'success': False, 'error': str(e)}

class PayPalService:
    @staticmethod
    def create_subscription(telegram_id: int):
        """Создать подписку через PayPal используя REST API и plan_id из payment_config"""
        try:
            access_token = get_paypal_access_token()
            url = PAYPAL_API_BASE + "/v1/billing/subscriptions"
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {access_token}"
            }
            data = {
                "plan_id": PAYPAL_PLAN_ID,
                "custom_id": str(telegram_id),
                "application_context": {
                    "brand_name": "Lash Course",
                    "locale": "en-US",
                    "shipping_preference": "NO_SHIPPING",
                    "user_action": "SUBSCRIBE_NOW",
                    "return_url": PAYPAL_RETURN_URL,
                    "cancel_url": PAYPAL_CANCEL_URL
                }
            }
            response = requests.post(url, headers=headers, json=data)
            response.raise_for_status()
            result = response.json()

            # Получаем ссылку для оплаты
            approval_url = next((link['href'] for link in result['links'] if link['rel'] == 'approve'), None)

            return {
                'success': True,
                'subscription_id': result.get('id'),
                'approval_url': approval_url
            }
        except Exception as e:
            logger.error(f"Ошибка создания подписки PayPal: {e}")
            return {'success': False, 'error': str(e)}

    @staticmethod
    def get_subscription(subscription_id: str):
        """Получить детали подписки PayPal"""
        try:
            access_token = get_paypal_access_token()
            url = PAYPAL_API_BASE + f"/v1/billing/subscriptions/{subscription_id}"
            headers = {"Authorization": f"Bearer {access_token}"}
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            return {'success': True, 'subscription': response.json()}
        except Exception as e:
            logger.error(f"Ошибка получения подписки PayPal: {e}")
            return {'success': False, 'error': str(e)}

    @staticmethod
    def cancel_subscription(subscription_id: str, reason="Canceled by user"):
        """Отменить подписку PayPal"""
        try:
            access_token = get_paypal_access_token()
            url = PAYPAL_API_BASE + f"/v1/billing/subscriptions/{subscription_id}/cancel"
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {access_token}"
            }
            data = {"reason": reason}
            response = requests.post(url, headers=headers, json=data)
            response.raise_for_status()
            return {'success': True}
        except Exception as e:
            logger.error(f"Ошибка отмены подписки PayPal: {e}")
            return {'success': False, 'error': str(e)}

def handle_stripe_payment_success(session):
    try:
        session_id = session.get('id')
        customer_id = session.get('customer')
        telegram_id = session.get('metadata', {}).get('telegram_id')

        if not customer_id:
            logger.warning(f"Customer ID отсутствует в session {session_id}, пробуем получить вручную.")
            if session.get('invoice'):
                invoice = stripe.Invoice.retrieve(session['invoice'])
                customer_id = invoice.get('customer')
                logger.info(f"Customer ID найден через invoice: {customer_id}")
            if not customer_id:
                full_session = stripe.checkout.Session.retrieve(session_id)
                customer_id = full_session.get('customer')
                logger.info(f"Customer ID найден через обновлённую session: {customer_id}")

        if not telegram_id:
            logger.error(f"Нет telegram_id в session metadata: {session_id}")
            return

        telegram_id = int(telegram_id)

        logger.info(f"Оплата успешна: telegram_id={telegram_id}, customer_id={customer_id}")

        activate_subscription(telegram_id, customer_id)

    except Exception as e:
        logger.exception(f"Ошибка при обработке успешной оплаты Stripe: {e}")

def verify_stripe_webhook(payload, sig_header):
    try:
        event = stripe.Webhook.construct_event(payload, sig_header, STRIPE_WEBHOOK_SECRET)
        return event
    except ValueError:
        return None
    except stripe.error.SignatureVerificationError:
        return None

def verify_paypal_webhook(headers, body) -> bool:
    """
    Проверка подписи webhook от PayPal через API.
    Возвращает True, если подпись валидна, иначе False.
    """

    transmission_id = headers.get('paypal-transmission-id')
    transmission_time = headers.get('paypal-transmission-time')
    cert_url = headers.get('paypal-cert-url')
    auth_algo = headers.get('paypal-auth-algo')
    transmission_sig = headers.get('paypal-transmission-sig')
    webhook_id = PAYPAL_WEBHOOK_ID  # ID вебхука в панели PayPal

    if not all([transmission_id, transmission_time, cert_url, auth_algo, transmission_sig, webhook_id]):
        return False

    verify_url = f"{PAYPAL_API_BASE}/v1/notifications/verify-webhook-signature"

    access_token = get_paypal_access_token()
    if not access_token:
        return False

    data = {
        "transmission_id": transmission_id,
        "transmission_time": transmission_time,
        "cert_url": cert_url,
        "auth_algo": auth_algo,
        "transmission_sig": transmission_sig,
        "webhook_id": webhook_id,
        "webhook_event": json.loads(body)
    }

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {access_token}"
    }

    response = requests.post(verify_url, json=data, headers=headers)
    if response.status_code == 200:
        verification_status = response.json().get('verification_status')
        return verification_status == 'SUCCESS'
    else:
        return False

def get_paypal_access_token() -> str | None:
    """
    Получение OAuth токена PayPal для вызова API.
    """
    url = f"{PAYPAL_API_BASE}/v1/oauth2/token"
    headers = {
        "Accept": "application/json",
        "Accept-Language": "en_US"
    }
    data = {
        "grant_type": "client_credentials"
    }

    response = requests.post(url, headers=headers, data=data, auth=(PAYPAL_CLIENT_ID, PAYPAL_CLIENT_SECRET))
    if response.status_code == 200:
        return response.json().get('access_token')
    else:
        return None
