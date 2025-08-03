from database import (
    get_db, create_user, get_user_by_telegram_id, update_user_onboarding,
    create_subscription, activate_subscription, cancel_subscription,
    get_active_subscription, get_subscription_by_id
)
from pprint import pprint

# ⚙️ Получаем сессию базы данных
database = next(get_db())

# 📌 1. Создание нового пользователя
user = create_user(
    database,
    telegram_id=12345678,
    username="nataliia",
    first_name="Nataliia",
    last_name="Petrychuk"
)
print("✅ Пользователь создан:")
pprint(vars(user))

# 📌 2. Обновление данных онбординга
user = update_user_onboarding(
    database,
    telegram_id=12345678,
    format_choice="video",
    level_choice="beginner",
    time_choice="morning",
    goal_choice="lashes"
)
print("✅ Онбординг обновлен:")
pprint(vars(user))

# 📌 3. Создание подписки
subscription = create_subscription(
    database,
    telegram_id=12345678,
    payment_system="paypal",
    subscription_id="sub_001",
    amount=29.99,
    customer_id="cust_001"
)
print("✅ Подписка создана:")
pprint(vars(subscription))

# 📌 4. Активация подписки
subscription = activate_subscription(database, "sub_001")
print("✅ Подписка активирована:")
pprint(vars(subscription))

# 📌 5. Получение активной подписки по Telegram ID
active_sub = get_active_subscription(database, 12345678)
print("📦 Активная подписка:")
pprint(vars(active_sub) if active_sub else "Нет активной подписки")

# 📌 6. Отмена подписки
cancelled = cancel_subscription(database, "sub_001")
print("🚫 Подписка отменена:")
pprint(vars(cancelled))

# 📌 7. Получение пользователя по Telegram ID
user = get_user_by_telegram_id(database, 12345678)
print("👤 Полученный пользователь:")
pprint(vars(user))

# 📌 8. Получение подписки по ID
sub = get_subscription_by_id(database, "sub_001")
print("🔍 Подписка по ID:")
pprint(vars(sub) if sub else "Не найдена")
