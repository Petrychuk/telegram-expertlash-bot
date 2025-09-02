
from __future__ import annotations
import os
import sys
import hmac
import hashlib
from datetime import datetime, timedelta

# --- .env ---
try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))
except Exception:
    pass

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

def test_env():
    print("\n🔍 Проверка ENV…")
    ok = True
    need = ["BOT_TOKEN", "JWT_SECRET"]
    optional = ["APP_URL", "GROUP_ID", "STRIPE_SECRET_KEY", "PAYPAL_CLIENT_ID", "PAYPAL_CLIENT_SECRET"]

    for k in need:
        v = os.getenv(k)
        if v:
            print(f"  ✅ {k} — OK")
        else:
            print(f"  ❌ {k} — отсутствует")
            ok = False

    for k in optional:
        v = os.getenv(k)
        if v:
            head = (v[:48] + "...") if len(v) > 48 else v
            print(f"  ℹ️  {k}: {head}")
        else:
            print(f"  ℹ️  {k}: (не задано)")

    return ok

def test_file_structure():
    print("\n🔍 Проверка структуры файлов…")
    required = [
        "config.py",
        "payment_config.py",
        "database.py",
        "payment_service.py",
        "telegram_service.py",
        "webhook.py",
        "main.py",
        "auth_telegram.py",
        "set_group_menu.py",
        "server.py",
        "tasks.py"
    ]
    ok = True
    for f in required:
        p = os.path.join(ROOT, f)
        if os.path.exists(p):
            print(f"  ✅ {f} найден")
        else:
            print(f"  ❌ {f} не найден")
            ok = False
    return ok

def test_database():
    print("\n🔍 Тестирование БД…")
    try:
        from database import create_tables, get_db, create_user, get_user_by_telegram_id

        create_tables()
        print("  ✅ Таблицы созданы/актуальны")

        db = next(get_db())
        try:
            tid = 123456789
            user = get_user_by_telegram_id(db, tid)
            if not user:
                user = create_user(db, tid, "testuser", "Test", "User")
                print(f"  ✅ Пользователь создан: id={user.id}")
            else:
                print(f"  ℹ️  Пользователь уже существует: id={user.id}")

            check = get_user_by_telegram_id(db, tid)
            if not check:
                print("  ❌ Пользователь не читается")
                return False
        finally:
            db.close()
        print("  ✅ БД OK")
        return True
    except Exception as e:
        print(f"  ❌ Ошибка БД: {e}")
        return False

def test_payment_config():
    print("\n🔍 Конфиг платежей…")
    try:
        from payment_config import (
            PAYPAL_CLIENT_ID, PAYPAL_CLIENT_SECRET, STRIPE_SECRET_KEY,
            SUBSCRIPTION_PRICE, CLOSED_GROUP_LINK
        )
        print(f"  ✅ Subscription Price: {SUBSCRIPTION_PRICE} EUR")
        print(f"  ✅ Closed Group Link: {CLOSED_GROUP_LINK}")
        # ключи могут быть пустыми на деве — не валим тест
        for name, val in [("PAYPAL_CLIENT_ID", PAYPAL_CLIENT_ID),
                          ("PAYPAL_CLIENT_SECRET", PAYPAL_CLIENT_SECRET),
                          ("STRIPE_SECRET_KEY", STRIPE_SECRET_KEY)]:
            head = (val or "")
            head = (head[:10] + "...") if head else "(empty)"
            print(f"  ℹ️  {name}: {head}")
        return True
    except Exception as e:
        print(f"  ❌ Ошибка конфига: {e}")
        return False

def test_payment_services():
    print("\n🔍 Сервисы платежей (ошибки сети допустимы)…")
    try:
        from payment_service import StripeService, PayPalService
        print("  ✅ Импорт StripeService/PayPalService")
        # Stripe
        try:
            res = StripeService.create_subscription_session(123456789)
            ok = res.get("success")
            print("  ✅ Stripe OK" if ok else f"  ⚠️  Stripe: {res.get('error')}")
        except Exception as e:
            print(f"  ⚠️  Stripe вызов упал: {e}")
        # PayPal
        try:
            res = PayPalService.create_subscription(123456789)
            ok = res.get("success")
            print("  ✅ PayPal OK" if ok else f"  ⚠️  PayPal: {res.get('error')}")
        except Exception as e:
            print(f"  ⚠️  PayPal вызов упал: {e}")
        return True
    except Exception as e:
        print(f"  ❌ Импорт платежей: {e}")
        return False

def test_auth_module():
    print("\n🔍 Модуль авторизации Telegram (подпись)…")
    try:
        import auth_telegram as at

        # синтетический init_data с известной подписью
        # образуем data без hash → затем вычислим hash как делает сервер
        fake_token = "123:ABC-example-bot-token"
        fields = {
            "auth_date": "1700000000",
            "query_id": "AAHhHhHhHhHh",
            "user": json_dumps_sorted({"id": 42, "username": "demo", "first_name": "Demo"}),
        }
        check_str = "\n".join(f"{k}={fields[k]}" for k in sorted(fields.keys()))
        secret = hashlib.sha256(fake_token.encode("utf-8")).digest()
        calc_hash = hmac.new(secret, check_str.encode("utf-8"), hashlib.sha256).hexdigest()
        init_data = "&".join([f"{k}={fields[k]}" for k in fields.keys()] + [f"hash={calc_hash}"])

        ok = at.check_telegram_auth(init_data, fake_token)
        if not ok:
            print("  ❌ check_telegram_auth вернул None на корректной подписи")
            return False
        print("  ✅ check_telegram_auth положительно валидирует корректную подпись")
        return True
    except Exception as e:
        print(f"  ❌ Ошибка auth-модуля: {e}")
        return False

def json_dumps_sorted(obj) -> str:
    import json
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":"), sort_keys=True)

def test_blueprints_and_routes():
    print("\n🔍 Flask blueprints / маршруты…")
    try:
        from webhook import app   # твой основной Flask
        routes = {rule.rule for rule in app.url_map.iter_rules()}
        expected = {"/webhook/stripe", "/webhook/paypal", "/health", "/api/auth/telegram", "/api/auth/test"}
        missing = expected - routes
        if missing:
            print(f"  ❌ Не найдены маршруты: {sorted(missing)}")
            # не валим весь проект, но возвращаем False — это важно
            return False
        print("  ✅ Все ключевые маршруты присутствуют")
        return True
    except Exception as e:
        print(f"  ❌ Ошибка импорта Flask app/webhook: {e}")
        return False

def test_telegram_service_stub():
    print("\n🔍 TelegramService (без сетевых запросов)…")
    try:
        from telegram_service import TelegramService
        svc = TelegramService()
        print(f"  ✅ TelegramService.api_url={svc.api_url[:48]}…")
        print("  ⚠️  Сетевые вызовы не выполняем в smoke")
        return True
    except Exception as e:
        print(f"  ❌ Ошибка TelegramService: {e}")
        return False

def main():
    print("🚀 Запуск SMOKE-проверки\n")
    tests = [
        ("ENV", test_env),
        ("Структура файлов", test_file_structure),
        ("База данных", test_database),
        ("Конфиг платежей", test_payment_config),
        ("Сервисы платежей", test_payment_services),
        ("Auth Telegram подпись", test_auth_module),
        ("Flask маршруты", test_blueprints_and_routes),
        ("TelegramService", test_telegram_service_stub),
    ]

    passed = 0
    for name, fn in tests:
        print("\n" + "=" * 60)
        print(f"Тест: {name}")
        print("=" * 60)
        try:
            if fn():
                passed += 1
                print(f"✅ {name}: ПРОЙДЕН")
            else:
                print(f"❌ {name}: НЕ ПРОЙДЕН")
        except Exception as e:
            print(f"❌ {name}: ОШИБКА — {e}")

    total = len(tests)
    print("\n" + "=" * 60)
    print("ИТОГИ")
    print("=" * 60)
    print(f"Пройдено: {passed}/{total}  ({passed/total*100:.1f}%)")
    print("🎉 Всё ок!" if passed == total else "⚠️  Есть проблемы выше.")
    return 0 if passed == total else 1

if __name__ == "__main__":
    sys.exit(main())
