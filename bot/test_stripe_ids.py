import stripe
import os
from dotenv import load_dotenv

from payment_config import STRIPE_CANCEL_URL, STRIPE_RETURN_URL, STRIPE_SECRET_KEY

load_dotenv()

stripe.api_key = os.getenv("STRIPE_SECRET_KEY")

telegram_id = 5379903145  # тестовый Telegram ID
user_email = "test@example.com"  # тестовый email

session = stripe.checkout.Session.create(
    success_url=STRIPE_RETURN_URL,
    cancel_url=STRIPE_CANCEL_URL,
    payment_method_types=["card"],
    mode="subscription",
    line_items=[{
        "price": "price_1Rs2wB6S8Oc0JZWfqIIhtXze",  # замени на свой test price_id из Stripe Dashboard
        "quantity": 1,
    }],
    customer_email=user_email,
    metadata={"telegram_id": telegram_id}
)

print("=== Полный ответ Stripe ===")
print(session)

print("\nCustomer ID:", session.get("customer"))
print("Metadata:", session.get("metadata"))
