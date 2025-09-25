# test_stripe_ids.py
import stripe
import sys, os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from payment_service import StripeService
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

# --- Тестовые данные ---
TEST_USER_ID = 12345 # Внутренний ID пользователя из вашей БД

def main():
    try:
        # Вызываем наш обновленный сервис, передавая user_id
        result = StripeService.create_subscription_session(user_id=TEST_USER_ID)

        if not result.get('success'):
            raise RuntimeError(result.get('error', 'Unknown error'))

        print("✅ Checkout Session создана")
        print("URL для тестовой оплаты (открой в браузере):")
        print(result['url'])
        print("\n=== Короткая сводка ===")
        print("session.id:", result['session_id'])
        print(f"metadata: {{'user_id': {TEST_USER_ID}}}") # Проверяем, что user_id будет передан

    except Exception as e:
        print("❌ Ошибка при создании Checkout Session:")
        print(e)

if __name__ == "__main__":
    main()
