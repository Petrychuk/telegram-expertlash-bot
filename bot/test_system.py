"""
Скрипт для тестирования системы подписок
"""
import os
import sys
from datetime import datetime, timedelta

# Добавляем текущую директорию в путь для импорта модулей
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def test_database_setup():
    """Тестирование настройки базы данных"""
    print("🔍 Тестирование настройки базы данных...")

    try:
        from database import create_tables, get_db, create_user, get_user_by_telegram_id

        # Создаем таблицы
        create_tables()
        print("✅ Таблицы созданы успешно")

        # Тестируем создание пользователя
        db = next(get_db())
        try:
            test_user = create_user(db, 123456789, "testuser", "Test", "User")
            print(f"✅ Пользователь создан: ID={test_user.id}, Telegram ID={test_user.telegram_id}")

            # Тестируем получение пользователя
            retrieved_user = get_user_by_telegram_id(db, 123456789)
            if retrieved_user:
                print(f"✅ Пользователь найден: {retrieved_user.first_name} {retrieved_user.last_name}")
            else:
                print("❌ Пользователь не найден")
                return False
        finally:
            db.close()

    except Exception as e:
        print(f"❌ Ошибка при тестировании БД: {str(e)}")
        return False

    return True


def test_payment_config():
    """Тестирование конфигурации платежных систем"""
    print("\n🔍 Тестирование конфигурации платежных систем...")

    try:
        from payment_config import (
            PAYPAL_CLIENT_ID, PAYPAL_CLIENT_SECRET, STRIPE_SECRET_KEY,
            SUBSCRIPTION_PRICE, CLOSED_GROUP_LINK
        )

        # Частично выводим ключи, чтобы не светить их целиком
        print(f"✅ PayPal Client ID: {PAYPAL_CLIENT_ID[:10]}...")
        print(f"✅ PayPal Client Secret: {PAYPAL_CLIENT_SECRET[:10]}...")
        print(f"✅ Stripe Secret Key: {STRIPE_SECRET_KEY[:10]}...")
        print(f"✅ Subscription Price: {SUBSCRIPTION_PRICE} EUR")
        print(f"✅ Closed Group Link: {CLOSED_GROUP_LINK}")

    except Exception as e:
        print(f"❌ Ошибка при тестировании конфигурации: {str(e)}")
        return False

    return True


def test_payment_services():
    """Тестирование сервисов платежных систем"""
    print("\n🔍 Тестирование сервисов платежных систем...")

    try:
        from payment_service import StripeService, PayPalService

        print("✅ StripeService импортирован успешно")
        print("✅ PayPalService импортирован успешно")

        # В этом тесте мы допускаем ошибки сети/ключей — задача проверить, что код корректно отлавливает их
        print("⚠️  Тестирование Stripe (возможна ожидаемая ошибка с тестовыми ключами):")
        stripe_result = StripeService.create_subscription_session(123456789)
        if stripe_result.get('success'):
            print(f"✅ Stripe: сессия создана (session_id={stripe_result.get('session_id')})")
        else:
            print(f"⚠️  Ожидаемая ошибка Stripe: {stripe_result.get('error')}")

        print("⚠️  Тестирование PayPal (возможна ожидаемая ошибка с тестовыми ключами):")
        paypal_result = PayPalService.create_subscription(123456789)
        if paypal_result.get('success'):
            print(f"✅ PayPal: подписка создана (id={paypal_result.get('subscription_id')})")
        else:
            print(f"⚠️  Ожидаемая ошибка PayPal: {paypal_result.get('error')}")

    except Exception as e:
        print(f"❌ Ошибка при тестировании сервисов: {str(e)}")
        return False

    return True


def test_subscription_workflow():
    """Тестирование полного workflow подписки"""
    print("\n🔍 Тестирование workflow подписки...")

    try:
        from database import (
            get_db, create_subscription, activate_subscription,
            cancel_subscription, get_active_subscription
        )

        db = next(get_db())
        try:
            # Создаем подписку (Stripe: кладём session_id как временный subscription_id)
            subscription = create_subscription(
                db, 123456789, "stripe", "test_session_123", 10.0, "test_customer_123"
            )
            if not subscription:
                print("❌ Не удалось создать подписку")
                return False

            print(f"✅ Подписка создана: ID={subscription.id}, Status={subscription.status}")

            # Активируем подписку по session_id (как это делает reconciliation)
            activated = activate_subscription(db, "test_session_123")
            if activated and activated.status == "active":
                print(f"✅ Подписка активирована: Status={activated.status}, Expires={activated.expires_at}")
            else:
                print("❌ Не удалось активировать подписку")
                return False

            # Проверяем активную подписку
            active_sub = get_active_subscription(db, 123456789)
            if active_sub:
                print(f"✅ Найдена активная подписка: ID={active_sub.id}")
            else:
                print("❌ Активная подписка не найдена")
                return False

            # Отменяем подписку
            cancelled = cancel_subscription(db, "test_session_123")
            if cancelled and cancelled.status == "cancelled":
                print(f"✅ Подписка отменена: Status={cancelled.status}")
            else:
                print("❌ Не удалось отменить подписку")
                return False

        finally:
            db.close()

    except Exception as e:
        print(f"❌ Ошибка при тестировании workflow: {str(e)}")
        return False

    return True


def test_telegram_service():
    """Тестирование Telegram сервиса"""
    print("\n🔍 Тестирование Telegram сервиса...")

    try:
        from telegram_service import TelegramService

        telegram_service = TelegramService()
        print("✅ TelegramService создан успешно")
        print(f"✅ API URL: {telegram_service.api_url[:50]}...")

        # Примечание: реальные запросы к Telegram API не делаем в тестах
        print("⚠️  Реальные запросы к Telegram API в тестах не выполняются")

    except Exception as e:
        print(f"❌ Ошибка при тестировании Telegram сервиса: {str(e)}")
        return False

    return True


def test_webhook_server():
    """Тестирование webhook сервера"""
    print("\n🔍 Тестирование webhook сервера...")

    try:
        # ВАЖНО: импортируем из webhook.py в корне
        from webhook import app

        print("✅ Flask приложение создано успешно")

        # Проверяем наличие маршрутов
        routes = [rule.rule for rule in app.url_map.iter_rules()]
        expected_routes = ['/webhook/stripe', '/webhook/paypal', '/health']

        for route in expected_routes:
            if route in routes:
                print(f"✅ Маршрут {route} найден")
            else:
                print(f"❌ Маршрут {route} не найден")
                return False

    except Exception as e:
        print(f"❌ Ошибка при тестировании webhook сервера: {str(e)}")
        return False

    return True


def check_file_structure():
    """Проверка структуры файлов"""
    print("\n🔍 Проверка структуры файлов...")

    required_files = [
        'config.py',
        'payment_config.py',
        'database.py',
        'payment_service.py',
        'telegram_service.py',
        'webhook.py',
        'main.py'
    ]

    ok = True
    for file in required_files:
        if os.path.exists(file):
            print(f"✅ {file} найден")
        else:
            print(f"❌ {file} не найден")
            ok = False

    return ok


def main():
    """Основная функция тестирования"""
    print("🚀 Запуск тестирования системы подписок\n")

    tests = [
        ("Структура файлов", check_file_structure),
        ("База данных", test_database_setup),
        ("Конфигурация платежей", test_payment_config),
        ("Сервисы платежей", test_payment_services),
        ("Workflow подписки", test_subscription_workflow),
        ("Telegram сервис", test_telegram_service),
        ("Webhook сервер", test_webhook_server),
    ]

    passed = 0
    total = len(tests)

    for test_name, test_func in tests:
        print(f"\n{'='*50}")
        print(f"Тест: {test_name}")
        print('='*50)

        try:
            if test_func():
                passed += 1
                print(f"✅ {test_name}: ПРОЙДЕН")
            else:
                print(f"❌ {test_name}: НЕ ПРОЙДЕН")
        except Exception as e:
            print(f"❌ {test_name}: ОШИБКА - {str(e)}")

    print(f"\n{'='*50}")
    print(f"РЕЗУЛЬТАТЫ ТЕСТИРОВАНИЯ")
    print('='*50)
    print(f"Пройдено: {passed}/{total}")
    print(f"Процент успеха: {(passed/total)*100:.1f}%")

    if passed == total:
        print("🎉 Все тесты пройдены успешно!")
    else:
        print("⚠️  Некоторые тесты не пройдены. Проверьте конфигурацию.")

    return passed == total


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
