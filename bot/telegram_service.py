# telegram_service.py 
import os
import asyncio
import aiohttp
from datetime import datetime, timedelta
from database import SessionLocal, Subscription, get_db # Импортируем get_db
from sqlalchemy import or_
from config import BOT_TOKEN as CONF_BOT_TOKEN
from payment_config import CLOSED_GROUP_LINK
import logging
from functools import wraps # Импортируем wraps для декоратора

logger = logging.getLogger(__name__ )

APP_URL = os.getenv("APP_URL") or os.getenv("FRONTEND_URL")
if APP_URL and not APP_URL.startswith("https://" ):
    logger.warning("APP_URL/FRONTEND_URL must be HTTPS. Current: %s", APP_URL)

# --- Декоратор для безопасной работы с БД (аналогично webhook.py) ---
def with_db_session(fn):
    @wraps(fn)
    async def wrapper(*args, **kwargs):
        db = next(get_db())
        try:
            # Для асинхронных функций используем await
            result = await fn(db, *args, **kwargs)
            db.commit()
            return result
        except Exception as e:
            db.rollback()
            logger.error(f"DB error in async task {fn.__name__}: {e}", exc_info=True)
            raise
        finally:
            db.close()
    return wrapper

def _platform_keyboard():
    """Клавиатура: WebApp если задан APP_URL, иначе fallback в группу"""
    # Итальянский: "📲 Apri la piattaforma" -> "📲 Открыть платформу"
    # Итальянский: "➡️ Accedi al gruppo chiuso Expert Lash" -> "➡️ Войти в закрытую группу Expert Lash"
    if APP_URL:
        return {"inline_keyboard": [[{"text": "📲 Открыть платформу", "web_app": {"url": APP_URL}}]]}
    return {"inline_keyboard": [[{"text": "➡️ Войти в закрытую группу Expert Lash", "url": CLOSED_GROUP_LINK}]]}

class TelegramService:
    # ... (методы __init__ и _post остаются без изменений, они написаны хорошо) ...
    def __init__(self):
        self.bot_token = os.getenv("BOT_TOKEN", CONF_BOT_TOKEN)
        if not self.bot_token:
            raise RuntimeError("BOT_TOKEN not set")
        self.api_url = f"https://api.telegram.org/bot{self.bot_token}"

    async def _post(self, method: str, json: dict ):
        try:
            timeout = aiohttp.ClientTimeout(total=15 )
            async with aiohttp.ClientSession(timeout=timeout ) as session:
                async with session.post(f"{self.api_url}/{method}", json=json) as resp:
                    text = await resp.text()
                    if resp.status == 200:
                        try: return await resp.json()
                        except Exception: logger.exception("Telegram JSON decode failed: %s", text[:200]); return None
                    logger.error("Telegram API error [%s]: %s — %s", method, resp.status, text[:200])
                    return None
        except Exception as e:
            logger.exception("Telegram API exception [%s]: %s", method, e)
            return None

    async def send_message(self, chat_id: int, text: str, reply_markup=None, parse_mode="HTML"):
        payload = {"chat_id": chat_id, "text": text, "parse_mode": parse_mode}
        if reply_markup: payload["reply_markup"] = reply_markup
        return await self._post("sendMessage", payload)

    async def send_payment_success_notification(self, telegram_id: int, subscription):
        try:
            if not subscription or getattr(subscription, "status", None) != "active":
                logger.warning(f"Skip success notification: subscription not active for telegram_id={telegram_id}")
                # Итальянский: "✅ Pagamento ricevuto. L’accesso sarà attivato dopo la conferma. Attendi per favore."
                # Русский: "✅ Платеж получен. Доступ будет активирован после подтверждения. Пожалуйста, подождите."
                await self.send_message(telegram_id, "✅ Платеж получен. Доступ будет активирован после подтверждения. Пожалуйста, подождите.")
                return

            # Итальянский: "🎉 <b>Congratulazioni! Il pagamento è andato a buon fine!</b>\n\nIl tuo abbonamento è attivo fino al: ...\nImporto: ...\n\nOra puoi accedere alla piattaforma."
            # Русский: "🎉 <b>Поздравляем! Платеж прошел успешно!</b>\n\nВаша подписка активна до: ...\nСумма: ...\n\nТеперь вы можете войти на платформу."
            text = (
                "🎉 <b>Поздравляем! Платеж прошел успешно!</b>\n\n"
                f"Ваша подписка активна до: {subscription.expires_at:%d.%m.%Y %H:%M}\n"
                f"Сумма: {subscription.amount} {subscription.currency}\n\n"
                "Теперь вы можете войти на платформу."
            )
            await self.send_message(telegram_id, text, _platform_keyboard())
        except Exception as e:
            logger.error(f"Error sending payment success notification: {e}")

    async def send_subscription_cancelled_notification(self, telegram_id: int):
        try:
            # Итальянский: "❌ <b>Il tuo abbonamento è stato annullato</b>\n\nL’accesso alla piattaforma è stato revocato.\n\nSe desideri riattivare l’abbonamento, usa il comando /start"
            # Русский: "❌ <b>Ваша подписка была отменена</b>\n\nДоступ к платформе был отозван.\n\nЕсли вы хотите возобновить подписку, используйте команду /start"
            text = (
                "❌ <b>Ваша подписка была отменена</b>\n\n"
                "Доступ к платформе был отозван.\n\n"
                "Если вы хотите возобновить подписку, используйте команду /start"
            )
            await self.send_message(telegram_id, text)
        except Exception as e:
            logger.error(f"Error sending subscription cancelled notification: {e}")

    async def send_subscription_renewed_notification(self, telegram_id: int, subscription):
        try:
            if not subscription or getattr(subscription, "status", None) != "active":
                logger.warning("Skip renewed notification: subscription not active")
                # Итальянский: "✅ Pagamento ricevuto. L’accesso sarà confermato dopo l’elaborazione."
                # Русский: "✅ Платеж получен. Доступ будет подтвержден после обработки."
                await self.send_message(telegram_id, "✅ Платеж получен. Доступ будет подтвержден после обработки.")
                return

            # Итальянский: "✅ <b>Abbonamento rinnovato con successo!</b>\n\nIl tuo abbonamento è stato esteso fino al: ...\nImporto addebitato: ...\n\nL’accesso alla piattaforma è stato mantenuto!"
            # Русский: "✅ <b>Подписка успешно продлена!</b>\n\nВаша подписка была продлена до: ...\nСписанная сумма: ...\n\nДоступ к платформе сохранен!"
            text = (
                "✅ <b>Подписка успешно продлена!</b>\n\n"
                f"Ваша подписка была продлена до: {subscription.expires_at:%d.%m.%Y %H:%M}\n"
                f"Списанная сумма: {subscription.amount} {subscription.currency}\n\n"
                "Доступ к платформе сохранен!"
            )
            await self.send_message(telegram_id, text, _platform_keyboard())
        except Exception as e:
            logger.error(f"Error sending subscription renewed notification: {e}")

    async def send_payment_failed_notification(self, telegram_id: int):
        try:
            # Итальянский: "⚠️ <b>Problema con il pagamento</b>\n\nNon è stato possibile effettuare l’addebito.\nPer favore, controlla i dati della tua carta o aggiorna il metodo di pagamento.\nSe il problema persiste, l’accesso ai corsi sarà sospeso."
            # Русский: "⚠️ <b>Проблема с оплатой</b>\n\nНе удалось произвести списание средств.\nПожалуйста, проверьте данные вашей карты или обновите способ оплаты.\nЕсли проблема не будет решена, доступ к курсам будет приостановлен."
            text = (
                "⚠️ <b>Проблема с оплатой</b>\n\n"
                "Не удалось произвести списание средств.\n"
                "Пожалуйста, проверьте данные вашей карты или обновите способ оплаты.\n"
                "Если проблема не будет решена, доступ к курсам будет приостановлен."
            )
            # Итальянский: "💳 Aggiorna metodo di pagamento" -> "💳 Обновить способ оплаты"
            # Итальянский: "📞 Contatta supporto" -> "📞 Связаться с поддержкой"
            reply_markup = {
                "inline_keyboard": [
                    [{"text": "💳 Обновить способ оплаты", "callback_data": "update_payment_method"}],
                    [{"text": "📞 Связаться с поддержкой", "url": "https://t.me/liudmylazhyltsova"}]
                ]
            }
            await self.send_message(telegram_id, text, reply_markup )
        except Exception as e:
            logger.error(f"Error sending payment failed notification: {e}")

    # ... (методы get_chat_member, ban_chat_member, unban_chat_member остаются без изменений) ...
    async def get_chat_member(self, chat_id: str, user_id: int): return await self._post("getChatMember", {"chat_id": chat_id, "user_id": user_id})
    async def ban_chat_member(self, chat_id: str, user_id: int): payload = {"chat_id": chat_id, "user_id": user_id}; res = await self._post("banChatMember", payload); return res if res else await self._post("kickChatMember", payload)
    async def unban_chat_member(self, chat_id: str, user_id: int): return await self._post("unbanChatMember", {"chat_id": chat_id, "user_id": user_id, "only_if_banned": True})

    async def send_subscription_expiry_warning(self, telegram_id: int, days_left: int):
        try:
            # Итальянский: "⏰ <b>Il tuo abbonamento scade tra {days_left} giorni.</b>\n\nAssicurati che il pagamento automatico sia attivo per non perdere l’accesso."
            # Русский: "⏰ <b>Ваша подписка истекает через {days_left} дней.</b>\n\nУбедитесь, что автоматический платеж активен, чтобы не потерять доступ."
            text = (
                f"⏰ <b>Ваша подписка истекает через {days_left} дня(ей).</b>\n\n"
                "Убедитесь, что автоматический платеж активен, чтобы не потерять доступ."
            )
            reply_markup = {
                "inline_keyboard": [
                    [{"text": "💳 Обновить способ оплаты", "callback_data": "update_payment_method"}],
                    [{"text": "📞 Поддержка", "url": "https://t.me/liudmylazhyltsova"}]
                ]
            }
            await self.send_message(telegram_id, text, reply_markup )
        except Exception as e:
            logger.error(f"Error sending subscription expiry warning: {e}")

    # ... (метод send_video остается без изменений) ...
    async def send_video(self, chat_id: int, file_id: str, caption: str, reply_markup=None, parse_mode="HTML"):
        # ...
        pass

    async def send_subscription_expired_goodbye(self, telegram_id: int, stripe_url: str | None = None, paypal_url: str | None = None):
        # Итальянский: "🙏 <b>Grazie per essere stata con noi!</b>\n\nLa tua sottoscrizione è scaduta e l’accesso è stato revocato.\nPuoi tornare quando vuoi — usa i pulsanti sotto per rinnovare o ricominciare."
        # Русский: "🙏 <b>Спасибо, что были с нами!</b>\n\nВаша подписка истекла, и доступ был отозван.\nВы можете вернуться в любое время — используйте кнопки ниже, чтобы продлить или начать заново."
        text = (
            "🙏 <b>Спасибо, что были с нами!</b>\n\n"
            "Ваша подписка истекла, и доступ был отозван.\n"
            "Вы можете вернуться в любое время — используйте кнопки ниже, чтобы продлить или начать заново."
        )
        buttons = []
        # Итальянский: "🔁 Riattiva con Stripe" -> "🔁 Продлить через Stripe"
        if stripe_url: buttons.append([{"text": "🔁 Продлить через Stripe", "url": stripe_url}])
        # Итальянский: "🅿️ Riattiva con PayPal" -> "🅿️ Продлить через PayPal"
        if paypal_url: buttons.append([{"text": "🅿️ Продлить через PayPal", "url": paypal_url}])
        # Итальянский: "🔄 Ricomincia da capo" -> "🔄 Начать заново"
        buttons.append([{"text": "🔄 Начать заново", "callback_data": "restart_onboarding"}])
        # Итальянский: "📞 Supporto" -> "📞 Поддержка"
        buttons.append([{"text": "📞 Поддержка", "url": "https://t.me/liudmylazhyltsova"}] )
        await self.send_message(telegram_id, text, {"inline_keyboard": buttons})

@with_db_session
async def manage_group_access(db): # <-- Принимает сессию db
    """Проверяет истекшие подписки и отзывает доступ."""
    telegram_service = TelegramService()
    expired_subs = db.query(Subscription).filter(
        Subscription.expires_at < datetime.utcnow(),
        Subscription.has_group_access.is_(True),
        Subscription.status == "active"
    ).all()
    
    for sub in expired_subs:
        sub.has_group_access = False
        sub.status = "expired"
        db.add(sub)
        await telegram_service.send_subscription_cancelled_notification(sub.telegram_id)

    if expired_subs:
        logger.info(f"Processed {len(expired_subs)} expired subscriptions")

async def manage_group_access_loop(interval_seconds=3600):
    """Бесконечный цикл для проверки истекших подписок."""
    while True:
        try:
            await manage_group_access()
        except Exception as e:
            logger.error(f"Error in manage_group_access_loop: {e}", exc_info=True)
        await asyncio.sleep(interval_seconds)

@with_db_session
async def send_expiry_warnings(db): 
    """Отправляет предупреждения о скором окончании подписки."""
    telegram_service = TelegramService()
    warning_date = datetime.utcnow() + timedelta(days=3)
    subs_to_warn = db.query(Subscription).filter(
        Subscription.expires_at <= warning_date,
        Subscription.expires_at > datetime.utcnow(),
        Subscription.status == "active",
        Subscription.has_group_access.is_(True),
        # Добавляем проверку, чтобы не спамить каждый час
        or_(Subscription.last_warned_at.is_(None), Subscription.last_warned_at < datetime.utcnow() - timedelta(days=1))
    ).all()

    for sub in subs_to_warn:
        days_left = max(0, (sub.expires_at - datetime.utcnow()).days)
        if days_left > 0:
            await telegram_service.send_subscription_expiry_warning(sub.telegram_id, days_left)
            sub.last_warned_at = datetime.utcnow() # Отмечаем, что предупреждение отправлено
    
    if subs_to_warn:
        logger.info(f"Sent expiry warnings to {len(subs_to_warn)} users")

