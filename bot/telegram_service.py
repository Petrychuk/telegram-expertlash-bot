import asyncio
import aiohttp
from datetime import datetime, timedelta
from database import SessionLocal, Subscription
from sqlalchemy import and_
from config import BOT_TOKEN
from payment_config import CLOSED_GROUP_LINK
import logging

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

class TelegramService:
    def __init__(self):
        self.bot_token = BOT_TOKEN
        self.api_url = f"https://api.telegram.org/bot{self.bot_token}"

    async def send_message(self, chat_id: int, text: str, reply_markup=None, parse_mode="HTML"):
        try:
            async with aiohttp.ClientSession() as session:
                data = {
                    'chat_id': chat_id,
                    'text': text,
                    'parse_mode': parse_mode
                }
                if reply_markup:
                    data['reply_markup'] = reply_markup
                async with session.post(f"{self.api_url}/sendMessage", json=data) as response:
                    if response.status == 200:
                        return await response.json()
                    else:
                        resp_text = await response.text()  # читаем тело ответа
                        logger.error(f"Error sending message: {response.status} — {resp_text}")
                        return None
        except Exception as e:
            logger.error(f"Error in send_message: {str(e)}")
            return None

    async def send_payment_success_notification(self, telegram_id: int, subscription):
        try:
            # Жёсткая защита: не шлём ссылку, если статус не active
            if not subscription or getattr(subscription, "status", None) != "active":
                logger.warning(f"Skip success notification: subscription not active "
                               f"(id={getattr(subscription, 'id', None)}, status={getattr(subscription, 'status', None)})")
                # Сообщение без ссылки (опционально)
                await self.send_message(
                    telegram_id,
                    "✅ Оплата получена. Доступ будет выдан после подтверждения. Пожалуйста, дождитесь сообщения."
                )
                return
            text = (
                "🎉 <b>Congratulazioni! Il pagamento è andato a buon fine!</b>\n\n"
                f"Il tuo abbonamento è attivo fino al: {subscription.expires_at.strftime('%d.%m.%Y %H:%M')}\n"
                f"Importo: {subscription.amount} {subscription.currency}\n\n"
                "Ora puoi accedere al gruppo chiuso con i corsi!"
            )
            reply_markup = {
                "inline_keyboard": [[
                    {
                        "text": "➡️ Accedi al gruppo chiuso Expert Lash",
                        "url": CLOSED_GROUP_LINK
                    }
                ]]
            }
            await self.send_message(telegram_id, text, reply_markup)
        except Exception as e:
            logger.error(f"Error sending payment success notification: {str(e)}")

    async def send_subscription_cancelled_notification(self, telegram_id: int):
        try:
            text = (
                "❌ <b>Il tuo abbonamento è stato annullato</b>\n\n"
                "L’accesso al gruppo chiuso con i corsi è stato revocato.\n\n"
                "Se desideri riattivare l’abbonamento, usa il comando /start"
            )
            await self.send_message(telegram_id, text)
        except Exception as e:
            logger.error(f"Error sending subscription cancelled notification: {str(e)}")

    async def send_subscription_renewed_notification(self, telegram_id: int, subscription):
        try:
            # Не отправляем ссылку, если почему-то статус не active
            if not subscription or getattr(subscription, "status", None) != "active":
                logger.warning(f"Skip renewed notification: subscription not active "
                               f"(id={getattr(subscription, 'id', None)}, status={getattr(subscription, 'status', None)})")
                await self.send_message(
                    telegram_id,
                    "✅ Оплата за продление получена. Доступ будет подтверждён после обработки. Пожалуйста, дождитесь сообщения."
                )
                return
            
            text = (
                "✅ <b>Abbonamento rinnovato con successo!</b>\n\n"
                f"Il tuo abbonamento è stato esteso fino al: {subscription.expires_at.strftime('%d.%m.%Y %H:%M')}\n"
                f"Importo addebitato: {subscription.amount} {subscription.currency}\n\n"
                "L’accesso al gruppo chiuso con i corsi è stato mantenuto!"
            )
            reply_markup = {
                "inline_keyboard": [[
                    {
                        "text": "➡️ Accedi al gruppo chiuso Expert Lash",
                        "url": CLOSED_GROUP_LINK
                    }
                ]]
            }
            await self.send_message(telegram_id, text, reply_markup)
        except Exception as e:
            logger.error(f"Error sending subscription renewed notification: {str(e)}")

    async def send_payment_failed_notification(self, telegram_id: int):
        try:
            text = (
                "⚠️ <b>Problema con il pagamento dell’abbonamento</b>\n\n"
                "Non è stato possibile effettuare l’addebito per il rinnovo dell’abbonamento.\n"
                "Per favore, controlla i dati della tua carta o aggiorna il metodo di pagamento.\n\n"
                "Se il problema non verrà risolto, l’accesso ai corsi potrebbe essere sospeso."
            )
            reply_markup = {
                "inline_keyboard": [
                    [{
                        "text": "💳 Aggiorna il metodo di pagamento",
                        "callback_data": "update_payment_method"
                    }],
                    [{
                        "text": "📞 Contatta il supporto",
                        "url": "https://t.me/liudmylazhyltsova"
                    }]
                ]
            }
            await self.send_message(telegram_id, text, reply_markup)
        except Exception as e:
            logger.error(f"Error sending payment failed notification: {str(e)}")

    async def get_chat_member(self, chat_id: str, user_id: int):
        try:
            async with aiohttp.ClientSession() as session:
                data = {
                    'chat_id': chat_id,
                    'user_id': user_id
                }
                async with session.post(f"{self.api_url}/getChatMember", json=data) as response:
                    if response.status == 200:
                        return await response.json()
                    else:
                        logger.error(f"Error getting chat member: {response.status}")
                        return None
        except Exception as e:
            logger.error(f"Error in get_chat_member: {str(e)}")
            return None

    async def kick_chat_member(self, chat_id: str, user_id: int):
        try:
            async with aiohttp.ClientSession() as session:
                data = {
                    'chat_id': chat_id,
                    'user_id': user_id
                }
                async with session.post(f"{self.api_url}/kickChatMember", json=data) as response:
                    if response.status == 200:
                        return await response.json()
                    else:
                        logger.error(f"Error kicking chat member: {response.status}")
                        return None
        except Exception as e:
            logger.error(f"Error in kick_chat_member: {str(e)}")
            return None

    async def unban_chat_member(self, chat_id: str, user_id: int):
        try:
            async with aiohttp.ClientSession() as session:
                data = {
                    'chat_id': chat_id,
                    'user_id': user_id,
                    'only_if_banned': True
                }
                async with session.post(f"{self.api_url}/unbanChatMember", json=data) as response:
                    if response.status == 200:
                        return await response.json()
                    else:
                        logger.error(f"Error unbanning chat member: {response.status}")
                        return None
        except Exception as e:
            logger.error(f"Error in unban_chat_member: {str(e)}")
            return None

    async def send_subscription_expiry_warning(self, telegram_id: int, days_left: int):
        try:
            text = (
                f"⏰ <b>Il tuo abbonamento scade tra {days_left} giorni.</b>\n\n"
                "Per non perdere l'accesso ai corsi, assicurati che il pagamento automatico sia attivo.\n\n"
                "Se hai domande, contatta il supporto."
            )
            reply_markup = {
                "inline_keyboard": [
                    [{
                        "text": "💳 Aggiorna il metodo di pagamento",
                        "callback_data": "update_payment_method"
                    }],
                    [{
                        "text": "📞 Contatta il supporto",
                        "url": "https://t.me/liudmylazhyltsova"
                    }]
                ]
            }
            await self.send_message(telegram_id, text, reply_markup)
        except Exception as e:
            logger.error(f"Error sending subscription expiry warning: {str(e)}")

async def manage_group_access():
    telegram_service = TelegramService()
    db = None
    try:
        db = SessionLocal()
        expired_subs = db.query(Subscription).filter(
            and_(
                Subscription.expires_at < datetime.utcnow(),
                Subscription.has_group_access == True,
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
        logger.error(f"Error in manage_group_access: {str(e)}")
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
    from database import SessionLocal, Subscription
    from sqlalchemy import and_

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
                Subscription.has_group_access == True
            )
        ).all()

        for sub in subs_to_warn:
            days_left = (sub.expires_at - datetime.utcnow()).days
            await telegram_service.send_subscription_expiry_warning(sub.telegram_id, days_left)

        logger.info(f"Sent expiry warnings to {len(subs_to_warn)} users")
    except Exception as e:
        logger.error(f"Error in send_expiry_warnings: {str(e)}")
    finally:
        if db:
            db.close()

# Пример запуска из синхронного контекста (например, из крона)
def run_manage_group_access():
    asyncio.run(manage_group_access())

def run_send_expiry_warnings():
    asyncio.run(send_expiry_warnings())
