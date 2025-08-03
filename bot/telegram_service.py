import asyncio
import aiohttp
from datetime import datetime
from config import BOT_TOKEN
from payment_config import CLOSED_GROUP_LINK

class TelegramService:
    def __init__(self):
        self.bot_token = BOT_TOKEN
        self.api_url = f"https://api.telegram.org/bot{self.bot_token}"
    
    async def send_message(self, chat_id: int, text: str, reply_markup=None, parse_mode="HTML"):
        """Отправка сообщения через Telegram API"""
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
                        print(f"Error sending message: {response.status}")
                        return None
        except Exception as e:
            print(f"Error in send_message: {str(e)}")
            return None
    
    async def send_payment_success_notification(self, telegram_id: int, subscription):
        """Отправка уведомления об успешной оплате"""
        try:
            text = (
                "🎉 <b>Congratulazioni! Il pagamento è andato a buon fine!</b>\n\n"  # 🎉 <b>Поздравляем! Оплата прошла успешно!</b>\n\n
                f"Il tuo abbonamento è attivo fino al: {subscription.expires_at.strftime('%d.%m.%Y %H:%M')}\n"  # Ваша подписка активирована до: ...
                f"Importo: {subscription.amount} {subscription.currency}\n\n"  # Сумма: ...
                "Ora puoi accedere al gruppo chiuso con i corsi!"  # Теперь вы можете перейти в закрытую группу с курсами!
            )
            
            # Создаем inline клавиатуру с кнопкой для перехода в группу
            reply_markup = {
                "inline_keyboard": [[
                    {
                        "text": "➡️ Accedi al gruppo chiuso Expert Lash", # Перейти в закрытую группу Expert Lash
                        "url": CLOSED_GROUP_LINK
                    }
                ]]
            }
            
            await self.send_message(telegram_id, text, reply_markup)
            
        except Exception as e:
            print(f"Error sending payment success notification: {str(e)}")
    
    async def send_subscription_cancelled_notification(self, telegram_id: int):
        """Отправка уведомления об отмене подписки"""
        try:
            text = (
                "❌ <b>Il tuo abbonamento è stato annullato</b>\n\n" # Ваша подписка была отменена.
                "L’accesso al gruppo chiuso con i corsi è stato revocato.\n\n" #Доступ к закрытой группе с курсами прекращён.
                "Se desideri riattivare l’abbonamento, usa il comando /start" # Если хотите возобновить подписку, используйте команду /start.
            )
            
            await self.send_message(telegram_id, text)
            
        except Exception as e:
            print(f"Error sending subscription cancelled notification: {str(e)}")
    
    async def send_subscription_renewed_notification(self, telegram_id: int, subscription):
        """Отправка уведомления о продлении подписки (авточардж)"""
        try:
            text = (
                
                "✅ <b>Abbonamento rinnovato con successo!</b>\n\n" # Подписка успешно продлена!
                f"Il tuo abbonamento è stato esteso fino al: {subscription.expires_at.strftime('%d.%m.%Y %H:%M')}\n" #Ваша подписка продлена до:
                f"Importo addebitato: {subscription.amount} {subscription.currency}\n\n" #Сумма списания:
                "L’accesso al gruppo chiuso con i corsi è stato mantenuto!" # Доступ к закрытой группе с курсами сохранен!
            )
            
            # Создаем inline клавиатуру с кнопкой для перехода в группу
            reply_markup = {
                "inline_keyboard": [[
                    {
                        "text": "➡️ Accedi al gruppo chiuso Expert Lash", # Перейти в закрытую группу Expert Lash
                        "url": CLOSED_GROUP_LINK
                    }
                ]]
            }
            
            await self.send_message(telegram_id, text, reply_markup)
            
        except Exception as e:
            print(f"Error sending subscription renewed notification: {str(e)}")
    
    async def send_payment_failed_notification(self, telegram_id: int):
        """Отправка уведомления о неуспешной оплате"""
        try:
            text = (
                "⚠️ <b>Problema con il pagamento dell’abbonamento</b>\n\n"  # ⚠️ Проблема с оплатой подписки
                "Non è stato possibile effettuare l’addebito per il rinnovo dell’abbonamento.\n"  # Не удалось списать средства для продления
                "Per favore, controlla i dati della tua carta o aggiorna il metodo di pagamento.\n\n"  # Пожалуйста, проверьте карту или способ оплаты
                "Se il problema non verrà risolto, l’accesso ai corsi potrebbe essere sospeso."  # Если не решить, доступ может быть приостановлен
            )
            
            # Создаем inline клавиатуру с кнопками для решения проблемы
            reply_markup = {
                "inline_keyboard": [
                    [{
                        "text": "💳 Aggiorna il metodo di pagamento",  # Обновить способ оплаты
                        "callback_data": "update_payment_method"
                    }],
                    [{
                        "text": "📞 Contatta il supporto",  # Связаться с поддержкой
                        "url": "https://t.me/liudmylazhyltsova"
                    }]
                ]
            }
            
            await self.send_message(telegram_id, text, reply_markup)
            
        except Exception as e:
            print(f"Error sending payment failed notification: {str(e)}")
    
    async def get_chat_member(self, chat_id: str, user_id: int):
        """Получение информации о участнике чата"""
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
                        return None
        except Exception as e:
            print(f"Error in get_chat_member: {str(e)}")
            return None
    
    async def kick_chat_member(self, chat_id: str, user_id: int):
        """Исключение участника из чата"""
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
                        print(f"Error kicking chat member: {response.status}")
                        return None
        except Exception as e:
            print(f"Error in kick_chat_member: {str(e)}")
            return None
    
    async def unban_chat_member(self, chat_id: str, user_id: int):
        """Разблокировка участника чата (позволяет ему снова присоединиться)"""
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
                        print(f"Error unbanning chat member: {response.status}")
                        return None
        except Exception as e:
            print(f"Error in unban_chat_member: {str(e)}")
            return None
    
    async def send_subscription_expiry_warning(self, telegram_id: int, days_left: int):
        """Отправка предупреждения о скором истечении подписки"""
        try:
            text = (
                f"⏰ <b>Il tuo abbonamento scade tra {days_left} giorni.</b>\n\n"  # ⏰ <b>Ваша подписка истекает через {days_left} дн.</b>
                "Per non perdere l'accesso ai corsi, assicurati che il pagamento automatico sia attivo.\n\n"  # Чтобы не потерять доступ к курсам, убедитесь, что у вас настроен автоплатеж.
                "Se hai domande, contatta il supporto."  # Если у вас есть вопросы, обратитесь в поддержку.
            )
            
            # Создаем inline клавиатуру с кнопками для решения проблемы
            reply_markup = {
                "inline_keyboard": [
                    [{
                        "text": "💳 Aggiorna il metodo di pagamento",  # Обновить способ оплаты
                        "callback_data": "update_payment_method"
                    }],
                    [{
                        "text": "📞 Contatta il supporto",  # Связаться с поддержкой
                        "url": "https://t.me/liudmylazhyltsova"
                    }]
                ]
            }
            
            await self.send_message(telegram_id, text, reply_markup)
            
        except Exception as e:
            print(f"Error sending subscription expiry warning: {str(e)}")

# Функция для автоматического управления доступом к группе
async def manage_group_access():
    """
    Функция для периодической проверки подписок и управления доступом к группе.
    Должна запускаться как фоновая задача (например, через cron или celery).
    """
    from database import get_db, SessionLocal
    from sqlalchemy import and_
    from database import Subscription
    
    telegram_service = TelegramService()
    
    try:
        db = SessionLocal()
        
        # Получаем все подписки, которые истекли, но пользователи еще имеют доступ к группе
        expired_subscriptions = db.query(Subscription).filter(
            and_(
                Subscription.expires_at < datetime.utcnow(),
                Subscription.has_group_access == True,
                Subscription.status == "active"
            )
        ).all()
        
        for subscription in expired_subscriptions:
            # Убираем доступ к группе
            subscription.has_group_access = False
            subscription.status = "expired"
            
            # Отправляем уведомление пользователю
            await telegram_service.send_subscription_cancelled_notification(
                subscription.telegram_id
            )
            
            # Если у вас есть ID группы, можно исключить пользователя
            # await telegram_service.kick_chat_member(GROUP_CHAT_ID, subscription.telegram_id)
        
        db.commit()
        print(f"Processed {len(expired_subscriptions)} expired subscriptions")
        
    except Exception as e:
        print(f"Error in manage_group_access: {str(e)}")
        db.rollback()
    finally:
        db.close()

# Функция для отправки предупреждений о скором истечении подписки
async def send_expiry_warnings():
    """
    Функция для отправки предупреждений пользователям о скором истечении подписки.
    Должна запускаться ежедневно.
    """
    from database import get_db, SessionLocal
    from sqlalchemy import and_
    from database import Subscription
    from datetime import timedelta
    
    telegram_service = TelegramService()
    
    try:
        db = SessionLocal()
        
        # Получаем подписки, которые истекают через 3 дня
        warning_date = datetime.utcnow() + timedelta(days=3)
        
        subscriptions_to_warn = db.query(Subscription).filter(
            and_(
                Subscription.expires_at <= warning_date,
                Subscription.expires_at > datetime.utcnow(),
                Subscription.status == "active",
                Subscription.has_group_access == True
            )
        ).all()
        
        for subscription in subscriptions_to_warn:
            days_left = (subscription.expires_at - datetime.utcnow()).days
            await telegram_service.send_subscription_expiry_warning(
                subscription.telegram_id, days_left
            )
        
        print(f"Sent expiry warnings to {len(subscriptions_to_warn)} users")
        
    except Exception as e:
        print(f"Error in send_expiry_warnings: {str(e)}")
    finally:
        db.close()
