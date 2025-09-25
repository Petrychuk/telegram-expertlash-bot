import sys, os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from payment_service import PayPalService

# --- Тестовые данные ---
TEST_USER_ID = 12345 # Внутренний ID пользователя из вашей БД

def main():
    try:
        # Вызываем наш обновленный сервис, передавая user_id
        result = PayPalService.create_subscription(user_id=TEST_USER_ID)

        if not result.get('success'):
            raise RuntimeError(result.get('error', 'Unknown error'))

        print("✅ Подписка создана (sandbox)")
        print("\n=== Короткая сводка ===")
        print("subscription.id:", result['subscription_id'])
        print("approval_url:", result['approval_url'])
        print(f"custom_id: {TEST_USER_ID}") # Проверяем, что user_id будет передан в custom_id

    except Exception as e:
        print("❌ Ошибка:", e)

if __name__ == "__main__":
    main()