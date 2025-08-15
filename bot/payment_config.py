
import os
from dotenv import load_dotenv

# ---------------------------
# Определение окружения
# ---------------------------
# Допускаем оба варианта: ENV и FLASK_ENV
ENV = (os.getenv("ENV") or os.getenv("FLASK_ENV") or "dev").lower()

# В проде не подхватываем локальный .env, во всех остальных — подхватываем
if ENV not in ("prod", "production"):
    load_dotenv()

def _must(name: str) -> str:
    v = os.getenv(name)
    if not v:
        raise RuntimeError(f"Missing required env var: {name}")
    return v

def _float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)))
    except ValueError:
        raise RuntimeError(f"Invalid float in env var {name}")

# ---------------------------
# PayPal
# ---------------------------
PAYPAL_CLIENT_ID     = _must("PAYPAL_CLIENT_ID")
PAYPAL_CLIENT_SECRET = _must("PAYPAL_CLIENT_SECRET")
PAYPAL_WEBHOOK_ID    = _must("PAYPAL_WEBHOOK_ID")
PAYPAL_RETURN_URL    = _must("PAYPAL_RETURN_URL")
PAYPAL_CANCEL_URL    = _must("PAYPAL_CANCEL_URL")

# ВАЖНО: для sandbox корректная база — api-m.sandbox.paypal.com
PAYPAL_API_BASE = os.getenv("PAYPAL_API_BASE") or (
    "https://api.paypal.com" if ENV in ("prod", "production") else "https://api-m.sandbox.paypal.com"
)

# План подписки (готовый Billing Plan/Subscription Plan в PayPal)
PAYPAL_PLAN_ID = _must("PAYPAL_PLAN_ID")

# ---------------------------
# Stripe
# ---------------------------
STRIPE_PUBLISHABLE_KEY = _must("STRIPE_PUBLISHABLE_KEY")
STRIPE_SECRET_KEY      = _must("STRIPE_SECRET_KEY")
STRIPE_WEBHOOK_SECRET  = _must("STRIPE_WEBHOOK_SECRET")
STRIPE_RETURN_URL      = _must("STRIPE_RETURN_URL")
STRIPE_CANCEL_URL      = _must("STRIPE_CANCEL_URL")

# Необязательный заранее созданный Price (если есть)
STRIPE_PRICE_ID = os.getenv("STRIPE_PRICE_ID")  # может быть None

# ---------------------------
# Общие
# ---------------------------
SUBSCRIPTION_PRICE = _float("SUBSCRIPTION_PRICE", 10.00)
CLOSED_GROUP_LINK  = _must("CLOSED_GROUP_LINK")
