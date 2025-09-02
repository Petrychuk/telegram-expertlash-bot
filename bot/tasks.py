import os
import asyncio
import logging
from datetime import datetime, timedelta
from sqlalchemy import and_, or_
from database import SessionLocal, Subscription
from telegram_service import TelegramService
from payment_service import StripeService, PayPalService
from config import VIDEO_PENDING_FILE_ID

# ---------- ЛОГИ ----------
logging.basicConfig(
    filename="subscription_checker.log",
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# ---------- ПАРАМЕТРЫ (можно переопределить переменными окружения) ----------
PENDING_MIN_AGE_HOURS  = int(os.getenv("PENDING_MIN_AGE_HOURS", "3"))   # когда «пинать» pending (сколько часов ждём после создания)
PENDING_COOLDOWN_HOURS = int(os.getenv("PENDING_COOLDOWN_HOURS", "24")) # как часто можно пинать одного и того же pending
WARN_DAYS_BEFORE       = int(os.getenv("WARN_DAYS_BEFORE", "2"))        # за сколько дней предупреждать active об окончании
SEND_CANCEL_NOTICE     = os.getenv("SEND_CANCEL_NOTICE", "1") == "1"    # слать ли уведомление при авто-деактивации
           
ADMIN_IDS = [s.strip() for s in os.getenv("ADMIN_IDS", "").split(",") if s.strip()]
ADMIN_FALLBACK_ID = int(ADMIN_IDS[0]) if ADMIN_IDS else None
DRY_RUN = os.getenv("DRY_RUN", "0") == "1" 

def _safe_chat_id(tid: int | None) -> int | None:
    """
    Когда DRY_RUN=1 — не трогаем БД и не дергаем платёжки.
    Если всё-таки хотим увидеть сообщение «вживую», подставим первого админа.
    """
    return ADMIN_FALLBACK_ID if DRY_RUN and ADMIN_FALLBACK_ID else tid
# =========================
# 1) ПИНАЕМ pending
# =========================
async def nudge_pending_subscriptions():
    """
    Находим pending-подписки достаточно «старые» и не пинали недавно.
    Отправляем видео-презентацию + кнопки «Оплатить» (Stripe/PayPal).
    """
    db = SessionLocal()
    ts = TelegramService()
    now = datetime.utcnow()
    cutoff_age   = now - timedelta(hours=PENDING_MIN_AGE_HOURS)
    cooldown_ago = now - timedelta(hours=PENDING_COOLDOWN_HOURS)

    try:
        pending = db.query(Subscription).filter(
            and_(
                Subscription.status == "pending",
                Subscription.created_at <= cutoff_age,
                or_(Subscription.last_nudge_at == None, Subscription.last_nudge_at <= cooldown_ago),
                Subscription.telegram_id != None
            )
        ).all()

        logger.info(f"[nudge_pending] candidates: {len(pending)}")

        for sub in pending:
            tid = sub.telegram_id

            stripe_url = None
            paypal_url = None

            if not DRY_RUN:
                # создаём ссылки оплаты
                try:
                    s = StripeService.create_subscription_session(tid)
                    if s.get("success"):
                        stripe_url = s.get("url")
                except Exception as e:
                    logger.error(f"[nudge_pending] stripe error for {tid}: {e}")

                try:
                    p = PayPalService.create_subscription(tid)
                    if p.get("success"):
                        paypal_url = p.get("approval_url")
                except Exception as e:
                    logger.error(f"[nudge_pending] paypal error for {tid}: {e}")

            # клавиатура
            buttons = []
            if stripe_url:
                buttons.append([{"text": "💳 Paga con Stripe", "url": stripe_url}])
            if paypal_url:
                buttons.append([{"text": "🅿️ Paga con PayPal", "url": paypal_url}])
            buttons.append([{"text": "📞 Consulenza", "url": "https://t.me/liudmylazhyltsova"}])
            reply_markup = {"inline_keyboard": buttons}

            caption = (
                "✨ <b>Lezione di prova</b>\n\n"
                "Guarda la presentazione e inizia quando vuoi.\n"
                "Scegli il metodo di pagamento qui sotto 👇"
            )

            # отправка видео (или лог в DRY_RUN)
            if DRY_RUN:
                logger.info(f"[nudge_pending][DRY_RUN] would send video to {tid}")
            else:
                chat_id = _safe_chat_id(tid)      # ниже helper, чтобы не падать
                try:
                    await ts.send_video(chat_id, VIDEO_PENDING_FILE_ID, caption, reply_markup)
                except Exception as e:
                    logger.error(f"[nudge_pending] send_video failed for {tid}: {e}")

            # отметим факт напоминания
            sub.last_nudge_at = now
            sub.nudges_count = (sub.nudges_count or 0) + 1
            db.add(sub)

        db.commit()

    except Exception as e:
        logger.error(f"[nudge_pending] exception: {e}")
        db.rollback()
    finally:
        db.close()
# =========================
# 2) ПРЕДУПРЕЖДАЕМ active
# =========================
async def warn_expiring_subscriptions():
    """
    Предупреждаем активных, когда до конца осталось <= WARN_DAYS_BEFORE.
    Используем готовый TelegramService.send_subscription_expiry_warning.
    """
    ts = TelegramService()
    db = SessionLocal()
    now = datetime.utcnow()
    warn_until = now + timedelta(days=WARN_DAYS_BEFORE)
    cooldown_ago = now - timedelta(hours=24)  # одно предупреждение в сутки максимум

    try:
        subs = db.query(Subscription).filter(
            and_(
                Subscription.status == "active",
                Subscription.expires_at != None,
                Subscription.expires_at > now,
                Subscription.expires_at <= warn_until,
                or_(Subscription.last_warned_at == None, Subscription.last_warned_at <= cooldown_ago),
                Subscription.telegram_id != None
            )
        ).all()

        logger.info(f"[warn_expiring] candidates: {len(subs)}")

        for sub in subs:
            days_left = max((sub.expires_at - now).days, 0)
            await ts.send_subscription_expiry_warning(_safe_chat_id(sub.telegram_id), days_left)
            sub.last_warned_at = now
            db.add(sub)

        db.commit()

    except Exception as e:
        logger.error(f"[warn_expiring] exception: {e}")
        db.rollback()
    finally:
        db.close()

# =========================
# 3) ДЕАКТИВИРУЕМ просроченные (твой кейс)
# =========================
async def deactivate_expired_subscriptions():
    """
    Выключаем доступ тем, у кого status=active, но expires_at < now.
    Отправляем тёплое прощальное сообщение с кнопками вернуться.
    """
    db = SessionLocal()
    now = datetime.utcnow()
    ts = TelegramService()

    try:
        logging.info("Запуск проверки подписок на истечение...")
        expired = db.query(Subscription).filter(
            and_(
                Subscription.status == "active",
                Subscription.expires_at != None,
                Subscription.expires_at < now
            )
        ).all()

        if not expired:
            logging.info("Нет просроченных подписок.")
            return
        # 1) меняем статус и закрываем доступ
        for sub in expired:
            logging.info(f"Деактивация подписки ID {sub.id} (user {sub.telegram_id})")
            sub.status = "expired"
            sub.has_group_access = False
            sub.cancelled_at = now
            db.add(sub)

        db.commit()

        # 2) после коммита — персональные сообщения
        for sub in expired:
            tid = _safe_chat_id(sub.telegram_id)
            stripe_url = paypal_url = None
            if not DRY_RUN:
            # пробуем сделать ссылки на «возврат» (если отвалится — просто не покажем кнопку)
                try:
                    s = StripeService.create_subscription_session(sub.telegram_id)
                    if s.get("success"):
                        stripe_url = s.get("url")
                except Exception as e:
                    logging.error(f"[goodbye] stripe error for {sub.telegram_id}: {e}")

                try:
                    p = PayPalService.create_subscription(sub.telegram_id)
                    if p.get("success"):
                        paypal_url = p.get("approval_url")
                except Exception as e:
                    logging.error(f"[goodbye] paypal error for {sub.telegram_id}: {e}")

                try:
                    await ts.send_subscription_expired_goodbye(_safe_chat_id(sub.telegram_id), stripe_url, paypal_url)
                except Exception as e:
                    logging.error(f"[goodbye] send failed for {sub.telegram_id}: {e}")

            logging.info(f"Завершено. Отключено подписок: {len(expired)}")

    except Exception as e:
        logging.error(f"[deactivate_expired_subscriptions] exception: {e}")
        db.rollback()
    finally:
        db.close()

# =========================
# Объединённый запуск
# =========================
async def run_all_jobs():
    start = datetime.utcnow()
    nudged = await nudge_pending_subscriptions()
    warned = await warn_expiring_subscriptions()
    expired = await deactivate_expired_subscriptions()
    # Отчёт админу 
    summary = (f"✅ Cron finished\n"
               f"- nudged pending: {nudged}\n"
               f"- warned active: {warned}\n"
               f"- deactivated expired: {expired}\n"
               f"took: {(datetime.utcnow()-start).total_seconds():.1f}s")
    if ADMIN_FALLBACK_ID:
        await TelegramService().send_message(ADMIN_FALLBACK_ID, summary)

def run_all_sync():
    asyncio.run(run_all_jobs())

if __name__ == "__main__":
    run_all_sync()
