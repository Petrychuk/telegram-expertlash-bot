import os
import random
import string
from pprint import pprint

from database import (
    create_tables, get_db, create_user, get_user_by_telegram_id, update_user_onboarding,
    create_subscription, activate_subscription, cancel_subscription,
    get_active_subscription, get_subscription_by_id, UserRole
)
from config import ADMIN_IDS

def to_dict(model):
    """Аккуратно сериализуем SQLAlchemy модель без служебного поля."""
    if not model:
        return None
    d = {k: v for k, v in vars(model).items() if k != "_sa_instance_state"}
    return d


def rand_suffix(n=4):
    return "".join(random.choices(string.ascii_lowercase + string.digits, k=n))


def main():
    print("🚀 Тест БД — полный цикл\n")

    # 0) Создаём таблицы
    create_tables()

    # 1) Получаем сессию
    db = next(get_db())

    # 2) Готовим уникальные тестовые данные
    suffix = rand_suffix()
    tg_id = int("12345678")  # можно поменять на один из ADMIN_IDS для проверки роли admin
    sub_id = f"sub_{suffix}"
    cust_id = f"cust_{suffix}"
    print(f"🧪 Используемые ID: telegram_id={tg_id}, subscription_id={sub_id}\n")

    try:
        # 3) Пользователь: создать или достать
        user = get_user_by_telegram_id(db, tg_id)
        if not user:
            user = create_user(
                db,
                telegram_id=tg_id,
                username=f"nataliia_{suffix}",
                first_name="Nataliia",
                last_name="Petrychuk"
            )
            print("✅ Пользователь создан:")
        else:
            print("ℹ️  Пользователь уже существует, используем существующего:")

        pprint(to_dict(user)); print()

        # 🔍 Проверка роли
        role = user.role if isinstance(user.role, str) else user.role.value
        role_status = "✅ admin" if str(tg_id) in ADMIN_IDS else "👩 student"
        print(f"🎭 Роль пользователя в БД: {role} ({role_status})\n")
        print(f"DEBUG: ADMIN_IDS = {ADMIN_IDS} (type={type(ADMIN_IDS)})")

        # 4) Онбординг
        user = update_user_onboarding(
            db,
            telegram_id=tg_id,
            format_choice="video",
            level_choice="beginner",
            time_choice="morning",
            goal_choice="lashes"
        )
        print("✅ Онбординг обновлён:")
        pprint(to_dict(user)); print()

        # 5) Создание подписки (pending)
        subscription = create_subscription(
            db,
            telegram_id=tg_id,
            payment_system="paypal",  # или "stripe"
            subscription_id=sub_id,   # в Stripe на этапе checkout это был бы session_id
            amount=29.99,
            customer_id=cust_id
        )
        print("✅ Подписка создана (pending):")
        pprint(to_dict(subscription)); print()

        # 6) Активация подписки
        subscription = activate_subscription(db, sub_id)
        print("✅ Подписка активирована:")
        pprint(to_dict(subscription)); print()

        # 7) Получение активной подписки по Telegram ID
        active_sub = get_active_subscription(db, tg_id)
        print("📦 Активная подписка:")
        pprint(to_dict(active_sub) or "Нет активной подписки"); print()

        # 8) Отмена подписки
        cancelled = cancel_subscription(db, sub_id)
        print("🚫 Подписка отменена:")
        pprint(to_dict(cancelled)); print()

        # 9) Получение пользователя по Telegram ID (ещё раз)
        user = get_user_by_telegram_id(db, tg_id)
        print("👤 Полученный пользователь:")
        pprint(to_dict(user)); print()

        # 10) Получение подписки по ID
        sub = get_subscription_by_id(db, sub_id)
        print("🔍 Подписка по ID:")
        pprint(to_dict(sub) if sub else "Не найдена"); print()

        print("🎉 Тест пройден без ошибок")

    except Exception as e:
        print(f"❌ Ошибка в тесте: {e}")
        raise
    finally:
        # 11) Закрываем сессию
        try:
            db.close()
        except Exception:
            pass

if __name__ == "__main__":
    main()
