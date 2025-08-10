# tasks.py
import logging
from datetime import datetime
from database import SessionLocal, Subscription

# Логирование
logging.basicConfig(
    filename="subscription_checker.log",
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)

def check_and_deactivate_subscriptions():
    """Проверка подписок и отключение доступа при истечении срока."""
    db = SessionLocal()
    now = datetime.utcnow()

    logging.info("Запуск проверки подписок...")

    # Ищем все активные подписки, срок которых уже истёк
    expired_subs = db.query(Subscription).filter(
        Subscription.status == "active",
        Subscription.expires_at < now
    ).all()

    if not expired_subs:
        logging.info("Нет просроченных подписок.")
        db.close()
        return

    for sub in expired_subs:
        logging.info(f"Деактивация подписки ID {sub.id} (пользователь {sub.telegram_id})")
        sub.status = "expired"
        sub.has_group_access = False
        db.add(sub)

    db.commit()
    db.close()
    logging.info(f"Завершено. Отключено подписок: {len(expired_subs)}")


if __name__ == "__main__":
    check_and_deactivate_subscriptions()
