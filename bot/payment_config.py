import os
from dotenv import load_dotenv

# Загружаем .env только в локалке
if os.getenv("ENV") != "production":
    load_dotenv()

# PayPal
PAYPAL_CLIENT_ID = os.getenv("PAYPAL_CLIENT_ID")
PAYPAL_CLIENT_SECRET = os.getenv("PAYPAL_CLIENT_SECRET")
PAYPAL_WEBHOOK_ID = os.getenv("PAYPAL_WEBHOOK_ID")
PAYPAL_RETURN_URL = os.getenv("PAYPAL_RETURN_URL")
PAYPAL_CANCEL_URL = os.getenv("PAYPAL_CANCEL_URL")
PAYPAL_API_BASE = os.getenv("PAYPAL_API_BASE")
PAYPAL_PLAN_ID = os.getenv("PAYPAL_PLAN_ID")

# Stripe
STRIPE_PUBLISHABLE_KEY = os.getenv("STRIPE_PUBLISHABLE_KEY")
STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET")
STRIPE_RETURN_URL = os.getenv("STRIPE_RETURN_URL")
STRIPE_CANCEL_URL = os.getenv("STRIPE_CANCEL_URL")

# Общие
SUBSCRIPTION_PRICE = float(os.getenv("SUBSCRIPTION_PRICE", "10.00"))
CLOSED_GROUP_LINK = os.getenv("CLOSED_GROUP_LINK")
