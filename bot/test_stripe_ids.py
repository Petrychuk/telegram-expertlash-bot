# test_stripe_ids.py
import stripe
from payment_config import (
    STRIPE_SECRET_KEY,
    STRIPE_RETURN_URL,
    STRIPE_CANCEL_URL,
    SUBSCRIPTION_PRICE,
)
try:
    from payment_config import STRIPE_PRICE_ID  # может отсутствовать
except Exception:
    STRIPE_PRICE_ID = None

stripe.api_key = STRIPE_SECRET_KEY

TELEGRAM_ID = 5379903145          # тестовый Telegram ID
USER_EMAIL  = "test@example.com"  # тестовый email

def get_or_create_price():
    """Возвращает готовый price_id. Если STRIPE_PRICE_ID не задан — создаёт Product/Price на лету."""
    if STRIPE_PRICE_ID:
        try:
            price = stripe.Price.retrieve(STRIPE_PRICE_ID)
            return price.id
        except Exception as e:
            print(f"⚠️  Не удалось получить STRIPE_PRICE_ID={STRIPE_PRICE_ID}: {e}\nСоздаю новый Price...")
    # Создаём продукт/цену на лету
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

def main():
    try:
        price_id = get_or_create_price()

        session = stripe.checkout.Session.create(
            # важно: возвращаемся с session_id для возможного reconcile
            success_url=f"{STRIPE_RETURN_URL}?session_id={{CHECKOUT_SESSION_ID}}",
            cancel_url=STRIPE_CANCEL_URL,
            mode="subscription",
            line_items=[{"price": price_id, "quantity": 1}],
            # Можно либо customer_email, либо создать кастомера отдельно.
            customer_email=USER_EMAIL,
            metadata={"telegram_id": str(TELEGRAM_ID)},
        )

        print("✅ Checkout Session создана")
        print("URL для тестовой оплаты (открой в браузере):")
        print(session.url)
        print("\n=== Короткая сводка ===")
        print("session.id:", session.id)
        print("subscription:", session.get("subscription"))  # может быть None до оплаты
        print("customer:", session.get("customer"))
        print("metadata:", session.get("metadata"))

    except Exception as e:
        print("❌ Ошибка при создании Checkout Session:")
        print(e)

if __name__ == "__main__":
    main()
