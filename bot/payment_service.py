# payment_service.py
import json
import logging
from typing import Optional, Dict, Any
import requests
from requests.auth import HTTPBasicAuth
import stripe
from payment_config import (
    STRIPE_SECRET_KEY,
    STRIPE_RETURN_URL,
    STRIPE_CANCEL_URL,
    SUBSCRIPTION_PRICE,
    PAYPAL_CLIENT_ID,
    PAYPAL_CLIENT_SECRET,
    PAYPAL_PLAN_ID,
    PAYPAL_RETURN_URL,
    PAYPAL_CANCEL_URL,
    PAYPAL_WEBHOOK_ID,
    STRIPE_WEBHOOK_SECRET, 
)

logger = logging.getLogger(__name__)

# =========================
# Stripe setup
# =========================
stripe.api_key = STRIPE_SECRET_KEY

# Необязательный ID заранее созданной цены.
# Если его нет в payment_config.py — создадим Price на лету.
try:
    from payment_config import STRIPE_PRICE_ID  # type: ignore
except Exception:
    STRIPE_PRICE_ID = None

# =========================
# PayPal setup
# =========================
# Если задан BASE в payment_config, используем его; иначе — sandbox.
PAYPAL_API_BASE = getattr(
    __import__("payment_config"),
    "PAYPAL_API_BASE",
    "https://api.sandbox.paypal.com",
)

# =========================
# PayPal helpers
# =========================
def get_paypal_access_token() -> Optional[str]:
    """
    Получить OAuth2 токен для PayPal API. Возвращает строку токена или None при ошибке.
    """
    url = f"{PAYPAL_API_BASE}/v1/oauth2/token"
    headers = {"Accept": "application/json", "Accept-Language": "en_US"}
    data = {"grant_type": "client_credentials"}

    try:
        resp = requests.post(
            url,
            headers=headers,
            data=data,
            auth=HTTPBasicAuth(PAYPAL_CLIENT_ID, PAYPAL_CLIENT_SECRET),
            timeout=30,
        )
        if resp.status_code == 200:
            token = resp.json().get("access_token")
            if not token:
                logger.error("PayPal token response without access_token field")
            return token
        logger.error(f"PayPal token error: {resp.status_code} {resp.text}")
    except Exception as e:
        logger.exception(f"PayPal token exception: {e}")
    return None
# =========================
# Stripe service
# =========================
class StripeService:
    @staticmethod
    def _get_or_create_price() -> str:
        """
        Возвращает ID Stripe Price.
        Если STRIPE_PRICE_ID не задан — создаёт Product/Price на лету.
        """
        if STRIPE_PRICE_ID:
            try:
                price = stripe.Price.retrieve(STRIPE_PRICE_ID)
                return price.id
            except Exception as e:
                logger.warning(f"Failed to retrieve STRIPE_PRICE_ID={STRIPE_PRICE_ID}: {e}. Will create a new Price.")

        # Создаём Product и Price на лету
        product = stripe.Product.create(
            name='Corso "Extension ciglia: da principiante a esperto"',
            description="Abbonamento mensile al corso di extension ciglia",
        )
        price = stripe.Price.create(
            product=product.id,
            unit_amount=int(SUBSCRIPTION_PRICE * 100),
            currency="eur",
            recurring={"interval": "month"},
        )
        return price.id

    @staticmethod
    def create_subscription_session(user_id: int, user_email: Optional[str] = None) -> Dict[str, Any]:
        """
        Создать Checkout Session для подписки (Stripe).
        """
        try:
            # создаём кастомера (email опционален)
            customer = stripe.Customer.create(
                email=user_email,
                metadata={"user_id": str(user_id)},
            )

            price_id = StripeService._get_or_create_price()

            session = stripe.checkout.Session.create(
                customer=customer.id,
                line_items=[{"price": price_id, "quantity": 1}],
                mode="subscription",
                success_url=STRIPE_RETURN_URL + "?session_id={CHECKOUT_SESSION_ID}",
                cancel_url=STRIPE_CANCEL_URL,
                metadata={"user_id": str(user_id)},
            )

            return {
                "success": True, "session_id": session.id,
                "url": session.url, "customer_id": customer.id,
            }
        except Exception as e:
            logger.exception(f"Stripe create session error: {e}")
            return {"success": False, "error": str(e)}

    @staticmethod
    def get_subscription_status(subscription_id: str) -> Dict[str, Any]:
        """Получить статус Stripe-подписки."""
        try:
            subscription = stripe.Subscription.retrieve(subscription_id)
            return {
                "success": True,
                "status": subscription.status,
                "current_period_end": subscription.current_period_end,
                "customer_id": subscription.customer,
            }
        except Exception as e:
            logger.exception(f"Stripe get_subscription_status error: {e}")
            return {"success": False, "error": str(e)}

    @staticmethod
    def cancel_subscription(subscription_id: str) -> Dict[str, Any]:
        """Отменить Stripe-подписку (в конце оплаченного периода)."""
        try:
            subscription = stripe.Subscription.modify(
                subscription_id, cancel_at_period_end=True
            )
            return {
                "success": True,
                "status": subscription.status,
                "cancel_at_period_end": subscription.cancel_at_period_end,
            }
        except Exception as e:
            logger.exception(f"Stripe cancel_subscription error: {e}")
            return {"success": False, "error": str(e)}

# =========================
# PayPal service
# =========================
class PayPalService:
    @staticmethod
    def create_subscription(user_id: int) -> Dict[str, Any]:
        """
        Создать подписку PayPal
        """
        try:
            token = get_paypal_access_token()
            if not token:
                return {"success": False, "error": "Failed to get PayPal token"}

            url = f"{PAYPAL_API_BASE}/v1/billing/subscriptions"
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {token}",
            }
            payload = {
                "plan_id": PAYPAL_PLAN_ID,
                "custom_id": str(user_id),
                "application_context": {
                    "brand_name": "Lash Course",
                    "locale": "en-US",
                    "shipping_preference": "NO_SHIPPING",
                    "user_action": "SUBSCRIBE_NOW",
                    "return_url": PAYPAL_RETURN_URL,
                    "cancel_url": PAYPAL_CANCEL_URL,
                },
            }

            resp = requests.post(url, headers=headers, json=payload, timeout=30)
            resp.raise_for_status()
            data = resp.json()

            approval_url = next(
                (link["href"] for link in data.get("links", []) if link.get("rel") == "approve"),
                None,
            )
            if not approval_url:
                logger.error(f"PayPal create_subscription: approve link not found: {data}")
                return {"success": False, "error": "Approve link not found"}

            return {
                "success": True,
                "subscription_id": data.get("id"),  # это resource.id, придёт в вебхуках
                "approval_url": approval_url,
            }
        except Exception as e:
            logger.exception(f"PayPal create_subscription error: {e}")
            return {"success": False, "error": str(e)}

    @staticmethod
    def get_subscription(subscription_id: str) -> Dict[str, Any]:
        """Получить детали PayPal-подписки."""
        try:
            token = get_paypal_access_token()
            if not token:
                return {"success": False, "error": "Failed to get PayPal token"}

            url = f"{PAYPAL_API_BASE}/v1/billing/subscriptions/{subscription_id}"
            headers = {"Authorization": f"Bearer {token}"}

            resp = requests.get(url, headers=headers, timeout=30)
            resp.raise_for_status()
            return {"success": True, "subscription": resp.json()}
        except Exception as e:
            logger.exception(f"PayPal get_subscription error: {e}")
            return {"success": False, "error": str(e)}

    @staticmethod
    def cancel_subscription(subscription_id: str, reason: str = "Canceled by user") -> Dict[str, Any]:
        """Отменить PayPal-подписку."""
        try:
            token = get_paypal_access_token()
            if not token:
                return {"success": False, "error": "Failed to get PayPal token"}

            url = f"{PAYPAL_API_BASE}/v1/billing/subscriptions/{subscription_id}/cancel"
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {token}",
            }
            payload = {"reason": reason}

            resp = requests.post(url, headers=headers, json=payload, timeout=30)
            resp.raise_for_status()
            return {"success": True}
        except Exception as e:
            logger.exception(f"PayPal cancel_subscription error: {e}")
            return {"success": False, "error": str(e)}

# =========================
# Webhook verifiers
# =========================
def verify_stripe_webhook(payload: bytes, sig_header: str):
    """
    Корректная верификация Stripe вебхука. Использует STRIPE_WEBHOOK_SECRET. Возвращает объект event (dict) или None.
    """
    try:
        event = stripe.Webhook.construct_event(
            payload=payload,
            sig_header=sig_header,
            secret=STRIPE_WEBHOOK_SECRET,
        )
        return event
    except Exception as e:
        logger.error(f"verify_stripe_webhook error: {e}")
        return None

def verify_paypal_webhook(headers: Dict[str, str], body) -> bool:
    """
    Проверка подписи PayPal вебхука через API.
    Возвращает True, если подпись валидна, иначе False.
    """
    # Достаём заголовки в обоих регистрах на всякий случай
    def h(key_low: str, key_cap: str) -> Optional[str]:
        return headers.get(key_low) or headers.get(key_cap)

    transmission_id = h("paypal-transmission-id", "PayPal-Transmission-Id")
    transmission_time = h("paypal-transmission-time", "PayPal-Transmission-Time")
    cert_url = h("paypal-cert-url", "PayPal-Cert-Url")
    auth_algo = h("paypal-auth-algo", "PayPal-Auth-Algo")
    transmission_sig = h("paypal-transmission-sig", "PayPal-Transmission-Sig")
    webhook_id = PAYPAL_WEBHOOK_ID

    if not all([transmission_id, transmission_time, cert_url, auth_algo, transmission_sig, webhook_id]):
        logger.error("verify_paypal_webhook: missing required headers/ids")
        return False

    token = get_paypal_access_token()
    if not token:
        logger.error("verify_paypal_webhook: failed to get token")
        return False

    verify_url = f"{PAYPAL_API_BASE}/v1/notifications/verify-webhook-signature"

    # body может быть bytes; приведём к dict
    try:
        if isinstance(body, (bytes, bytearray)):
            event_json = json.loads(body.decode("utf-8"))
        elif isinstance(body, str):
            event_json = json.loads(body)
        else:
            event_json = body or {}
    except Exception:
        event_json = {}

    payload = {
        "transmission_id": transmission_id,
        "transmission_time": transmission_time,
        "cert_url": cert_url,
        "auth_algo": auth_algo,
        "transmission_sig": transmission_sig,
        "webhook_id": webhook_id,
        "webhook_event": event_json,
    }
    headers_out = {"Content-Type": "application/json", "Authorization": f"Bearer {token}"}

    try:
        resp = requests.post(verify_url, json=payload, headers=headers_out, timeout=30)
        if resp.status_code == 200:
            status = resp.json().get("verification_status")
            ok = status == "SUCCESS"
            if not ok:
                logger.error(f"verify_paypal_webhook: status={status}, resp={resp.text}")
            return ok
        logger.error(f"verify_paypal_webhook: http {resp.status_code} {resp.text}")
        return False
    except Exception as e:
        logger.exception(f"verify_paypal_webhook exception: {e}")
        return False
