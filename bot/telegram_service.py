import os
import asyncio
import aiohttp
from datetime import datetime, timedelta
from database import SessionLocal, Subscription
from sqlalchemy import and_
from config import BOT_TOKEN as CONF_BOT_TOKEN
from payment_config import CLOSED_GROUP_LINK
import logging

logger = logging.getLogger(__name__)

APP_URL = os.getenv("APP_URL") or os.getenv("FRONTEND_URL")
if APP_URL and not APP_URL.startswith("https://"):
    logger.warning("APP_URL/FRONTEND_URL must be HTTPS. Current: %s", APP_URL)

def _platform_keyboard():
    """Клавиатура: WebApp если задан APP_URL, иначе fallback в группу"""
    if APP_URL:
        return {"inline_keyboard": [[{"text": "📲 Apri la piattaforma", "web_app": {"url": APP_URL}}]]}
    return {"inline_keyboard": [[{"text": "➡️ Accedi al gruppo chiuso Expert Lash", "url": CLOSED_GROUP_LINK}]]}

class TelegramService:
    def __init__(self):
        self.bot_token = os.getenv("BOT_TOKEN", CONF_BOT_TOKEN)
        if not self.bot_token:
            raise RuntimeError("BOT_TOKEN not set")
        self.api_url = f"https://api.telegram.org/bot{self.bot_token}"

    # ---- low-level helper ----
    async def _post(self, method: str, json: dict):
        try:
            timeout = aiohttp.ClientTimeout(total=15)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(f"{self.api_url}/{method}", json=json) as resp:
                    text = await resp.text()
                    if resp.status == 200:
                        try:
                            return await resp.json()
                        except Exception:
                            logger.exception("Telegram JSON decode failed: %s", text[:200])
                            return None
                    logger.error("Telegram API error [%s]: %s — %s", method, resp.status, text[:200])
                    return None
        except Exception as e:
            logger.exception("Telegram API exception [%s]: %s", method, e)
            return None

    # ---- messaging ----
    async def send_message(self, chat_id: int, text: str, reply_markup=None, parse_mode="HTML"):
        payload = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": parse_mode
        }
        if reply_markup:
            payload["reply_markup"] = reply_markup
        return await self._post("sendMessage", payload)

    async def send_payment_success_notification(self, telegram_id: int, subscription):
        try:
            if not subscription or getattr(subscription, "status", None) != "active":
                logger.warning(
                    "Skip success notification: subscription not active "
                    f"(id={getattr(subscription, 'id', None)}, status={getattr(subscription, 'status', None)})"
                )
                await self.send_message(
                    telegram_id,
                    "✅ Pagamento ricevuto. L’accesso sarà attivato dopo la conferma. Attendi per favore."
                )
                return

            text = (
                "🎉 <b>Congratulazioni! Il pagamento è andato a buon fine!</b>\n\n"
                f"Il tuo abbonamento è attivo fino al: {subscription.expires_at:%d.%m.%Y %H:%M}\n"
                f"Importo: {subscription.amount} {subscription.currency}\n\n"
                "Ora puoi accedere alla piattaforma."
            )
            await self.send_message(telegram_id, text, _platform_keyboard())
        except Exception as e:
            logger.error(f"Error sending payment success notification: {e}")

    async def send_subscription_cancelled_notification(self, telegram_id: int):
        try:
            text = (
                "❌ <b>Il tuo abbonamento è stato annullato</b>\n\n"
                "L’accesso alla piattaforma è stato revocato.\n\n"
                "Se desideri riattivare l’abbonamento, usa il comando /start"
            )
            await self.send_message(telegram_id, text)
        except Exception as e:
            logger.error(f"Error sending subscription cancelled notification: {e}")

    async def send_subscription_renewed_notification(self, telegram_id: int, subscription):
        try:
            if not subscription or getattr(subscription, "status", None) != "active":
                logger.warning("Skip renewed notification: subscription not active")
                await self.send_message(
                    telegram_id,
                    "✅ Pagamento ricevuto. L’accesso sarà confermato dopo l’elaborazione."
                )
                return

            text = (
                "✅ <b>Abbonamento rinnovato con successo!</b>\n\n"
                f"Il tuo abbonamento è stato esteso fino al: {subscription.expires_at:%d.%m.%Y %H:%M}\n"
                f"Importo addebitato: {subscription.amount} {subscription.currency}\n\n"
                "L’accesso alla piattaforma è stato mantenuto!"
            )
            await self.send_message(telegram_id, text, _platform_keyboard())
        except Exception as e:
            logger.error(f"Error sending subscription renewed notification: {e}")

    async def send_payment_failed_notification(self, telegram_id: int):
        try:
            text = (
                "⚠️ <b>Problema con il pagamento</b>\n\n"
                "Non è stato possibile effettuare l’addebito.\n"
                "Per favore, controlla i dati della tua carta o aggiorna il metodo di pagamento.\n"
                "Se il problema persiste, l’accesso ai corsi sarà sospeso."
            )
            reply_markup = {
                "inline_keyboard": [
                    [{"text": "💳 Aggiorna metodo di pagamento", "callback_data": "update_payment_method"}],
                    [{"text": "📞 Contatta supporto", "url": "https://t.me/liudmylazhyltsova"}]
                ]
            }
            await self.send_message(telegram_id, text, reply_markup)
        except Exception as e:
            logger.error(f"Error sending payment failed notification: {e}")

    # ---- membership helpers ----
    async def get_chat_member(self, chat_id: str, user_id: int):
        return await self._post("getChatMember", {"chat_id": chat_id, "user_id": user_id})

    async def ban_chat_member(self, chat_id: str, user_id: int):
        payload = {"chat_id": chat_id, "user_id": user_id}
        res = await self._post("banChatMember", payload)
        if not res:  # fallback
            res = await self._post("kickChatMember", payload)
        return res

    async def unban_chat_member(self, chat_id: str, user_id: int):
        return await self._post("unbanChatMember", {"chat_id": chat_id, "user_id": user_id, "only_if_banned": True})

    async def send_subscription_expiry_warning(self, telegram_id: int, days_left: int):
        try:
            text = (
                f"⏰ <b>Il tuo abbonamento scade tra {days_left} giorni.</b>\n\n"
                "Assicurati che il pagamento automatico sia attivo per non perdere l’accesso."
            )
            reply_markup = {
                "inline_keyboard": [
                    [{"text": "💳 Aggiorna metodo di pagamento", "callback_data": "update_payment_method"}],
                    [{"text": "📞 Supporto", "url": "https://t.me/liudmylazhyltsova"}]
                ]
            }
            await self.send_message(telegram_id, text, reply_markup)
        except Exception as e:
            logger.error(f"Error sending subscription expiry warning: {e}")

    # ---- видео и напоминания ----
    async def send_video(self, chat_id: int, file_id: str, caption: str,
                         reply_markup=None, parse_mode="HTML"):
        try:
            timeout = aiohttp.ClientTimeout(total=15)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                data = {"chat_id": chat_id, "video": file_id, "caption": caption, "parse_mode": parse_mode}
                if reply_markup:
                    data["reply_markup"] = reply_markup
                async with session.post(f"{self.api_url}/sendVideo", json=data) as resp:
                    txt = await resp.text()
                    if resp.status == 200:
                        return await resp.json()
                    logger.error(f"Error send_video: {resp.status} — {txt[:200]}")
                    return None
        except Exception as e:
            logger.error(f"Error in send_video: {str(e)}")
            return None

    async def send_subscription_expired_goodbye(self, telegram_id: int, stripe_url: str | None = None, paypal_url: str | None = None):
        text = (
            "🙏 <b>Grazie per essere stata con noi!</b>\n\n"
            "La tua sottoscrizione è scaduta e l’accesso è stato revocato.\n"
            "Puoi tornare quando vuoi — usa i pulsanti sotto per rinnovare o ricominciare."
        )
        buttons = []
        if stripe_url:
            buttons.append([{"text": "🔁 Riattiva con Stripe", "url": stripe_url}])
        if paypal_url:
            buttons.append([{"text": "🅿️ Riattiva con PayPal", "url": paypal_url}])
        buttons.append([{"text": "🔄 Ricomincia da capo", "callback_data": "restart_onboarding"}])
        buttons.append([{"text": "📞 Supporto", "url": "https://t.me/liudmylazhyltsova"}])
        await self.send_message(telegram_id, text, {"inline_keyboard": buttons})

# ---- periodics ----
async def manage_group_access():
    telegram_service = TelegramService()
    db = None
    try:
        db = SessionLocal()
        expired_subs = db.query(Subscription).filter(
            and_(
                Subscription.expires_at < datetime.utcnow(),
                Subscription.has_group_access.is_(True),
                Subscription.status == "active"
            )
        ).all()
        for sub in expired_subs:
            sub.has_group_access = False
            sub.status = "expired"
            db.add(sub)
            await telegram_service.send_subscription_cancelled_notification(sub.telegram_id)

        db.commit()
        logger.info(f"Processed {len(expired_subs)} expired subscriptions")
    except Exception as e:
        logger.error(f"Error in manage_group_access: {e}")
        if db:
            db.rollback()
    finally:
        if db:
            db.close()

async def manage_group_access_loop(interval_seconds=3600):
    while True:
        await manage_group_access()
        await asyncio.sleep(interval_seconds)

async def send_expiry_warnings():
    telegram_service = TelegramService()
    db = None
    try:
        db = SessionLocal()
        warning_date = datetime.utcnow() + timedelta(days=3)
        subs_to_warn = db.query(Subscription).filter(
            and_(
                Subscription.expires_at <= warning_date,
                Subscription.expires_at > datetime.utcnow(),
                Subscription.status == "active",
                Subscription.has_group_access.is_(True)
            )
        ).all()
        for sub in subs_to_warn:
            days_left = max(0, (sub.expires_at - datetime.utcnow()).days)
            await telegram_service.send_subscription_expiry_warning(sub.telegram_id, days_left)

        logger.info(f"Sent expiry warnings to {len(subs_to_warn)} users")
    except Exception as e:
        logger.error(f"Error in send_expiry_warnings: {e}")
    finally:
        if db:
            db.close()

def run_manage_group_access():
    asyncio.run(manage_group_access())

def run_send_expiry_warnings():
    asyncio.run(send_expiry_warnings())
