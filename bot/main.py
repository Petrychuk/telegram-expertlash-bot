import os
import asyncio
import logging
import threading
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, types
from aiogram.types import ( InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton)
from aiogram.utils import executor
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.contrib.fsm_storage.memory import MemoryStorage

from config import BOT_TOKEN, VIDEO_PRESENTATION_FILE_ID, VIDEO_REVIEWS
from payment_config import SUBSCRIPTION_PRICE, CLOSED_GROUP_LINK
from database import (
    create_tables, get_db, get_user_by_telegram_id, create_user, 
    update_user_onboarding, create_subscription, get_active_subscription
)

from payment_service import StripeService, PayPalService
from telegram_service import TelegramService, manage_group_access_loop

from webhook import app

# 1. Загрузка .env и инициализация
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
bot     = Bot(token=BOT_TOKEN, parse_mode="HTML")
FLASK_ENV = os.getenv("FLASK_ENV", "dev")

storage = MemoryStorage()
dp      = Dispatcher(bot, storage=storage)

# Создаем таблицы при запуске
create_tables()

# 2. Описание состояний онбординга
class Onboarding(StatesGroup):
    format = State()  # выбор формата
    level  = State()  # уровень
    time    = State()  # время
    goal    = State()  # цель
    promo_choice = State()  # пробный урок/биография/отзывы
    final_choice = State()  # я с вами/консультация
    payment_method = State() # выбор способа оплаты
    payment_status = State() # Новое состояние для статуса оплаты

# 3. Вспомогательная функция для Inline клавиатур
def create_inline_keyboard(buttons, prefix, row_width=2):
    kb = InlineKeyboardMarkup(row_width=row_width)
    for label, data_value in buttons:
        kb.insert(InlineKeyboardButton(label, callback_data=f"{prefix}:{data_value}"))
    return kb

# 4. Функция для создания постоянной Reply клавиатуры
def get_main_reply_keyboard():
    kb = ReplyKeyboardMarkup(resize_keyboard=True, one_time_keyboard=False)
    kb.add(KeyboardButton("🔄 Ricomincia da capo"), KeyboardButton("💳 Il mio abbonamento"))  # 🔄 Начать заново , Новая кнопка: Моя подписка
    kb.add(KeyboardButton("⭐ Recensioni"), KeyboardButton("📞 Consulenza"))  # ⭐ Отзывы, 📞 Консультация  # Новая кнопка: Моя подписка
    return kb

# 5. Функция для безопасной отправки видео
async def send_video_or_placeholder(message, file_id, caption, placeholder_text):    
    if file_id and file_id.strip():
        try:
            await message.answer_video(file_id, caption=caption)
        except Exception as e:
            # Если не удалось отправить видео, отправляем заглушку
            await message.answer(f"🎬 {placeholder_text}\n\n<i>Il video non è temporaneamente disponibile</i>")  # 🎬 {placeholder_text}\n\n<i>Видео временно недоступно</i>
    else:
        # Отправляем заглушку если file_id не задан
        await message.answer(f"🎬 {placeholder_text}\n\n<i>Il video non è temporaneamente disponibile</i>")  # 🎬 {placeholder_text}\n\n<i>Видео временно недоступно</i>

# 6. Функция для работы с базой данных
def get_or_create_user(telegram_id: int, username: str = None, first_name: str = None, last_name: str = None):    
    # Получение или создание пользователя
    db = next(get_db())
    try:
        user = get_user_by_telegram_id(db, telegram_id)
        if not user:
            user = create_user(db, telegram_id, username, first_name, last_name)
        return user
    finally:
        db.close()
        
# 7. Старт онбординга
@dp.message_handler(commands=["start"], state="*")
async def cmd_start(msg: types.Message, state: FSMContext):
    await state.finish() # Сбрасываем состояние при старте
     
     # Создаем или получаем пользователя в БД
    user = get_or_create_user(
        telegram_id=msg.from_user.id,
        username=msg.from_user.username,
        first_name=msg.from_user.first_name,
        last_name=msg.from_user.last_name
    )    
    await Onboarding.format.set()
     
     # Устанавливаем Reply-кнопки отдельным сообщением с текстом
    await msg.answer("💡 <i>Per una navigazione rapida, usa i pulsanti nel pannello in basso:</i>", reply_markup=get_main_reply_keyboard()) # Для быстрой навигации используйте кнопки в нижней панели:
    
    # Inline-кнопки для формата обучения
    format_kb = create_inline_keyboard([
    ("📹 Video lezioni", "video"),       #  Видео-уроки
    ("🎯 Webinar pratici", "webinar")    #  Практические вебинары
    ], prefix="format", row_width=2)
    
    # Отправляем основное сообщение с Inline-кнопками
    await msg.answer(
    f"👋 Ciao, {msg.from_user.first_name}! Sono la tua assistente per il corso «Ciglia: da principiante a esperta».\n\n"  # 👋 Привет, {msg.from_user.first_name}! Я — твой помощник по курсу «Ресницы от нуля до эксперта».
    "Facciamo conoscenza!\n\n"  # Давай познакомимся!
    "In quale formato preferisci studiare?\n\n",  # В каком формате ты предпочитаешь учиться?
    reply_markup=format_kb
)
   
# 8. Обработка формата
@dp.callback_query_handler(lambda c: c.data.startswith("format:"), state=Onboarding.format)
async def process_format(c: types.CallbackQuery, state: FSMContext):
    chosen_format = c.data.split(":", 1)[1]
    await state.update_data(format=chosen_format)
    await Onboarding.next()  # level
    
    # Inline-кнопки для уровня
    level_kb = create_inline_keyboard([
    ("🌱 Completamente principiante", "newbie"),         # 🌱 Совершенный новичок
    ("💪 Ho già esperienza", "experienced"),             # 💪 У меня уже есть опыт
    ("🚀 Voglio migliorare il mio livello", "improve")   # 🚀 Хочу повысить уровень работ
    ], prefix="level", row_width=1)
    
    await c.message.answer(
    "Fantastico! Qual è il tuo livello attuale nell'allungamento delle ciglia?",  # Здорово! А какой у тебя сейчас уровень в наращивании ресниц?
    reply_markup=level_kb
    )
    await c.answer()

# 9. Уровень
@dp.callback_query_handler(lambda c: c.data.startswith("level:"), state=Onboarding.level)
async def process_level(c: types.CallbackQuery, state: FSMContext):
    chosen_level = c.data.split(":", 1)[1]
    await state.update_data(level=chosen_level)
    await Onboarding.next()  # time
    
    # Inline-кнопки для времени
    time_kb = create_inline_keyboard([
    ("⏰ 1–2 ore a settimana", "1-2h"),     # ⏰ 1–2 ч в неделю
    ("⏳ 3–5 ore", "3-5h"),                # ⏳ 3–5 ч
    ("🔥 Più di 5 ore", "5+h")            # 🔥 Более 5 ч
    ], prefix="time", row_width=3)
    
    await c.message.answer(
    "Perfetto! Quanto tempo alla settimana sei disposto/a a dedicare allo studio?",  # Отлично! Сколько времени в неделю ты готов(а) уделять обучению?
    reply_markup=time_kb
    )
    await c.answer()
    
# 10. Время
@dp.callback_query_handler(lambda c: c.data.startswith("time:"), state=Onboarding.time)
async def process_time(c: types.CallbackQuery, state: FSMContext):
    chosen_time = c.data.split(":", 1)[1]
    await state.update_data(time=chosen_time)
    await Onboarding.next()  # goal
    
    # Inline-кнопки для цели
    goal_kb = create_inline_keyboard([
        ("💼 Lavorare come lash maker", "master"),             # 💼 Работать мастером
        ("💅 Imparare per uso personale", "for_self"),         # 💅 Научиться для себя
        ("🏢 Avviare una propria attività", "own_business")    # 🏢 Открыть своё дело
    ], prefix="goal", row_width=1)

    await c.message.answer(
    "Perfetto. Raccontami qual è il tuo obiettivo principale?",  # Отлично. Расскажи, пожалуйста, какая твоя главная цель?
    reply_markup=goal_kb
    )
    await c.answer()

# 11. Цель
@dp.callback_query_handler(lambda c: c.data.startswith("goal:"), state=Onboarding.goal)
async def process_goal(c: types.CallbackQuery, state: FSMContext):
    chosen_goal = c.data.split(":", 1)[1]
    await state.update_data(goal=chosen_goal)
    await Onboarding.next()  # promo_choice
    
    # Inline-кнопки для промо выбора
    promo_kb = create_inline_keyboard([
        ("🎬 Sì, mandami una lezione di prova", "trial_lesson"),        # 🎬 Да, прислать пробный урок
        ("👩‍🏫 Biografia di Liudmila", "ludmila_bio"),                  # 👩‍🏫 Биография Людмилы
        ("⭐ Recensioni reali sul corso", "course_reviews")              # ⭐ Реальные отзывы о курсе
    ], prefix="promo", row_width=1)

    await c.message.answer(
    "Fantastico! Abbiamo una lezione di prova gratuita per farti vedere la qualità del materiale.\n\n"  # Супер! У нас есть бесплатный пробный урок, чтобы ты убедился(ась) в качестве материала.
    "Vuoi ricevere subito il link?",  # Хочешь сразу получить ссылку на него?
    reply_markup=promo_kb
     )
    await c.answer()

# 12. Промо выбор (пробный урок/биография/отзывы)
@dp.callback_query_handler(lambda c: c.data.startswith("promo:"), state=Onboarding.promo_choice)
async def process_promo_choice(c: types.CallbackQuery, state: FSMContext):
    chosen_promo = c.data.split(":", 1)[1]
    await state.update_data(promo_choice=chosen_promo)
    await Onboarding.next()  # final_choice
    
    # Обработка выбора
    if chosen_promo == "trial_lesson":
        # Безопасно отправляем пробный урок
        await send_video_or_placeholder(
            c.message,
            VIDEO_PRESENTATION_FILE_ID,
            "Ti invio un breve video con una lezione di prova...\n\nGuardalo e fammi sapere cosa ne pensi!",  # Отправляю короткое видео с пробным уроком...\n\nПосмотри и дай знать, что думаешь!
            "Lezione di prova – presentazione del corso"  # Пробный урок - презентация курса
        )
    elif chosen_promo == "ludmila_bio":
        # Отправляем биографию
        await c.message.answer(
            "👩‍🏫 <b>Ljudmyla – La Tua Guida nel Mondo dell'Estetica Moderna</b>\n\n"
            "Sono Ljudmyla, ucraina e vivo in Italia dal 2014. Nel mondo dell'estetica lavoro con passione e dedizione, e posso affermare che non mi fermo mai nella mia crescita professionale. Ho partecipato a più di 30 corsi di formazione presso diverse Accademie in Europa, raggiungendo traguardi significativi.\n\n"
            "<b>I Miei Successi Professionali:</b>\n"
            "• Master di trucco permanente\n"
            "• Istruttrice certificata per extension ciglia\n"
            "• Rappresento l'Accademia Otchenash Sviato Academy in Sicilia\n"
            "• Autrice del mio corso per lashmaker 'Lashmaker 360°'\n"
            "• Organizzatrice di masterclass del trucco permanente\n"
            "• Vincitrice del campionato italiano di laminazione delle ciglia\n"
            "• Partecipante al campionato e conferenza Inter Permanent 2019\n"
            "• Partecipante alla conferenza Tallinn 2021 presso Sviato Academy\n"
            "• Titolare del titolo di stilista presso Sviato Academy.\n\n"
            "<b>Nel 2023:</b>\n"
            "• Ho tenuto più di 15 corsi su diverse tecniche di estensione delle ciglia e trucco permanente\n"
            "• Ho ricevuto il titolo di Top lash trainer & top 10 permanent make up Stylist secondo IBA Beauty Award XV\n"
            "• Ho sviluppato il mio marchio di prodotti per extension ciglia 'Ljudmyla Lashmaker's Line'\n"
            "• Ho partecipato alla fiera professionale B&F Show Catania con il mio brand.\n\n"
            "Ljudmyla ti aiuterà a padroneggiare la professione da zero o a migliorare le tue competenze!"
        )
    elif chosen_promo == "course_reviews":
        # Безопасно отправляем отзывы
        # ⭐ <b>Реальные отзывы наших учениц:</b>
        await c.message.answer("⭐ <b>Recensioni reali delle nostre studentesse:</b>")
        for i, (key, file_id) in enumerate(VIDEO_REVIEWS.items(), 1):
            await send_video_or_placeholder(
                c.message,
                file_id,
                f"Recensione {i}",               # Отзыв {i}
                f"Recensione della studentessa n.{i}"  # Отзыв ученицы №{i}
            )
    
    # Финальные кнопки
    final_kb = create_inline_keyboard([
       ("😊 Ci sto!", "join"),    # 😊 Я с вами! 
       ("📞 Prenota una consulenza", "consultation")   # 📞 Записаться на консультацию
    ], prefix="final", row_width=1)
    
    await c.message.answer(
        "Sei pronta a studiare con noi?",  # Ты готова с нами учиться?
        reply_markup=final_kb
    )
    await c.answer()

# 13. Финальный выбор
@dp.callback_query_handler(lambda c: c.data.startswith("final:"), state=Onboarding.final_choice)
async def process_final_choice(c: types.CallbackQuery, state: FSMContext):
    chosen_final = c.data.split(":", 1)[1]
    
    # Получаем все данные пользователя
    user_data = await state.get_data()
    
     # Сохраняем данные онбординга в БД
    db = next(get_db())
    try:
        update_user_onboarding(
            db, 
            c.from_user.id,
            user_data.get('format'),
            user_data.get('level'),
            user_data.get('time'),
            user_data.get('goal')
        )
    finally:
        db.close()
    
    if chosen_final == "join":
        # Предлагаем выбор способа оплаты
        payment_method_kb = create_inline_keyboard([
            ("PayPal", "paypal"),
            ("Stripe (Visa, Mastercard)", "stripe")
        ], prefix="payment_method", row_width=1)
        
        await c.message.answer(
            f"🎉 <b>Fantastico! Benvenuta al corso!</b>\n\n"  # 🎉 <b>Отлично! Добро пожаловать в курс!</b>\n\n
            f"Prezzo dell’abbonamento: <b>{SUBSCRIPTION_PRICE} EUR al mese</b>\n"  # Стоимость подписки: <b>{SUBSCRIPTION_PRICE} EUR в месяц</b>\n
            f"<b>L’abbonamento è valido per 1 mese dalla data di acquisto.</b>\n"  # <b>Подписка действует 1 месяц с момента покупки.</b>\n
            "Dopo il pagamento avrai accesso a tutti i materiali del corso.\n\n"  # После оплаты ты получишь доступ ко всем материалам курса.\n\n
            "Per favore, scegli il metodo di pagamento che preferisci:",  # Пожалуйста, выбери удобный способ оплаты:
            reply_markup=payment_method_kb

        )
        await Onboarding.payment_method.set()
        await c.answer()
        
    elif chosen_final == "consultation":
        # Переводим на консультацию с Людмилой
        consultation_kb = InlineKeyboardMarkup(row_width=1).add(
            InlineKeyboardButton("📞 Contatta Liudmila", url="https://t.me/liudmylazhyltsova"),  # 📞 Связаться с Людмилой
            InlineKeyboardButton("📱 WhatsApp: +39 329 887 0826", url="https://wa.me/393298870826")  # 📱 WhatsApp: +39 329 887 0826
        )
        
        await c.message.answer(
            "📞 <b>Sto prenotando una consulenza personalizzata!</b>\n\n"  # 📞 <b>Записываю на персональную консультацию!</b>\n\n
            "Liudmila risponderà a tutte le tue domande e ti aiuterà a scegliere il piano di studio migliore.\n\n"  # Людмила ответит на все твои вопросы и поможет выбрать оптимальный план обучения.\n\n
            "Contattala nel modo che preferisci:",  # Свяжись с ней удобным способом:
            reply_markup=consultation_kb
)
        await state.finish()
        await c.answer()

# 14. Обработка выбора способа оплаты
@dp.callback_query_handler(lambda c: c.data.startswith("payment_method:"), state=Onboarding.payment_method)
async def process_payment_method(c: types.CallbackQuery, state: FSMContext):
    chosen_method = c.data.split(":", 1)[1]
    await state.update_data(payment_method=chosen_method)

    if chosen_method == "stripe":
        # Создаем сессию Stripe
        result = StripeService.create_subscription_session(c.from_user.id)
        
        if result['success']:
            # Сохраняем подписку в БД
            db = next(get_db())
            try:
                create_subscription(
                    db, 
                    c.from_user.id, 
                    payment_system="stripe", 
                    subscription_id=result['session_id'], 
                    amount=SUBSCRIPTION_PRICE,
                    customer_id=result.get('customer_id')
                )
            finally:
                db.close()
            
            payment_link_kb = InlineKeyboardMarkup(row_width=1).add(
                # Кнопка для перехода к оплате
                InlineKeyboardButton("💳 Procedi al pagamento", url=result['url']) # перейти к оплате

            )
            
            # Вы выбрали Stripe. Перейдите по ссылке для оплаты:
            # После оплаты вы автоматически получите доступ к закрытой группе.
            await c.message.answer(
                "Hai scelto Stripe. Segui il link per effettuare il pagamento:\n\n"
                "Dopo il pagamento riceverai automaticamente l'accesso al gruppo privato.",
                reply_markup=payment_link_kb
            )

        else:
            # ❌ Ошибка при создании платежа: {result['error']}
            # Попробуйте еще раз или выберите другой способ оплаты.
            await c.message.answer(
                f"❌ Errore durante la creazione del pagamento: {result['error']}\n\n"
                "Riprova oppure scegli un altro metodo di pagamento."
            )
           
    elif chosen_method == "paypal":
        # Создаем подписку PayPal
        result = PayPalService.create_subscription(c.from_user.id)
        
        if result['success']:
            # Сохраняем подписку в БД
            db = next(get_db())
            try:
                create_subscription(
                    db, 
                    c.from_user.id, 
                    payment_system="paypal", 
                    subscription_id=result['subscription_id'],  # pay attention: 'subscription_id' from PayPal response
                    amount=SUBSCRIPTION_PRICE
                )
            finally:
                db.close()
            
            payment_link_kb = InlineKeyboardMarkup(row_width=1).add(
                InlineKeyboardButton("🅿️ Procedi al pagamento", url=result['approval_url']) #Перейти к оплате
            )
            
            # Вы выбрали PayPal. Перейдите по ссылке для оплаты:
            # После оплаты вы автоматически получите доступ к закрытой группе.
            await c.message.answer(
                "Hai scelto PayPal. Segui il link per effettuare il pagamento:\n\n"
                "Dopo il pagamento riceverai automaticamente l'accesso al gruppo privato.",
                reply_markup=payment_link_kb
            )

        else:
            # ❌ Ошибка при создании платежа: {result['error']}
            # Попробуйте еще раз или выберите другой способ оплаты.
            await c.message.answer(
                f"❌ Errore durante la creazione del pagamento: {result['error']}\n\n"
                "Riprova oppure scegli un altro metodo di pagamento."
            )
    
    await state.finish()
    await c.answer()
    
# 15. Обработка кнопки "Начать заново"
@dp.message_handler(text="🔄 Ricomincia da capo", state="*")  # 🔄 Начать заново
async def restart_onboarding(msg: types.Message, state: FSMContext):
    await cmd_start(msg, state)  # Перезапускаем онбординг

# 16. Обработка кнопки "Отзывы"
@dp.message_handler(text="⭐ Recensioni", state="*")  # ⭐ Отзывы
async def show_reviews(msg: types.Message):
    await msg.answer("⭐ <b>Recensioni reali delle nostre studentesse:</b>")  # ⭐ <b>Реальные отзывы наших учениц:</b>
    for i, (key, file_id) in enumerate(VIDEO_REVIEWS.items(), 1):
        await send_video_or_placeholder(
            msg,
            file_id,
            f"Recensione {i}",               # Отзыв {i}
            f"Recensione della studentessa n.{i}"  # Отзыв ученицы №{i}
        )

# 17. Обработка кнопки "Консультация"
@dp.message_handler(text="📞 Consulenza", state="*")  # 📞 Консультация
async def show_consultation_info(msg: types.Message):
    consultation_kb = InlineKeyboardMarkup(row_width=1).add(
        InlineKeyboardButton("📞 Contatta Liudmila", url="https://t.me/liudmylazhyltsova"),  # 📞 Связаться с Людмилой
        InlineKeyboardButton("📱 WhatsApp: +39 329 887 0826", url="https://wa.me/393298870826")  # 📱 WhatsApp: +39 329 887 0826
    )
    await msg.answer(
        "📞 <b>Sto prenotando una consulenza personalizzata!</b>\n\n"  # 📞 <b>Записываю на персональную консультацию!</b>\n\n
        "Liudmila risponderà a tutte le tue domande e ti aiuterà a scegliere il piano di studio migliore.\n\n"  # Людмила ответит на все твои вопросы и поможет выбрать оптимальный план обучения.\n\n
        "Contattala nel modo che preferisci:",  # Свяжись с ней удобным способом:
        reply_markup=consultation_kb
    )

# 18. Обработка кнопки "Моя подписка"
@dp.message_handler(text="💳 Il mio abbonamento", state="*")
async def show_my_subscription(msg: types.Message, state: FSMContext):
    db = next(get_db())
    try:
        user = get_user_by_telegram_id(db, msg.from_user.id)
        if not user:
           
            # ❌ На данный момент у вас нет активной подписки.
            # Вы можете оформить доступ к нашему закрытому сообществу всего за {SUBSCRIPTION_PRICE}€ в месяц.
            # Выберите способ оплаты:
            await msg.answer(
                f"❌ Al momento non hai un abbonamento attivo.\n\n"
                f"Puoi ottenere l'accesso alla nostra community privata per soli {SUBSCRIPTION_PRICE}€ al mese.\n\n"
                "Scegli il metodo di pagamento:",
            )

            await Onboarding.payment_method.set()  # <- Добавь это!
            return

        subscription = get_active_subscription(db, msg.from_user.id)
        if subscription:
            start_date = subscription.created_at.strftime('%d.%m.%Y') if subscription.created_at else "—"
            end_date = subscription.expires_at.strftime('%d.%m.%Y') if subscription.expires_at else "—"
            order_id = getattr(subscription, "order_id", getattr(subscription, "payment_id", "—"))

            await msg.answer(
                f"💳 <b>La tua sottoscrizione è attiva!</b>\n\n"
                f"📅 Data di attivazione: <b>{start_date}</b>\n"
                f"🔢 Numero ordine: <b>{order_id}</b>\n"
                f"⏳ Valida fino al: <b>{end_date}</b>\n\n"
                f"✅ Grazie per essere con noi!"
            )
        else:
            await msg.answer(
                f"❌ Al momento non hai un abbonamento attivo.\n\n"
                f"Puoi ottenere l'accesso alla nostra community privata per soli {SUBSCRIPTION_PRICE}€ al mese.\n\n"
                "Scegli il metodo di pagamento:",
                reply_markup=create_inline_keyboard([
                    ("PayPal", "paypal"),
                    ("Stripe (Visa, Mastercard)", "stripe")
                ], prefix="payment_method", row_width=1)
            )
            await Onboarding.payment_method.set()  # <- И здесь тоже!
    finally:
        db.close()
# 19. Обработка любых других сообщений в процессе онбординга
@dp.message_handler(state="*")
async def handle_other_messages(msg: types.Message, state: FSMContext):
    current_state = await state.get_state()
    if current_state is None:
        await msg.answer(
            "Ciao! Per iniziare, premi /start\n\n"  # Привет! Чтобы начать, нажми /start\n\n
            "Ti aiuterò a scegliere il formato di studio più adatto al corso «Ciglia da principiante a esperta»!"  # Я помогу тебе выбрать подходящий формат обучения на курсе «Ресницы от нуля до эксперта»!
        )
    else:
        await msg.answer(
            "Per favore, scegli una delle opzioni proposte usando i pulsanti qui sotto 👇"  # Пожалуйста, выбери один из предложенных вариантов с помощью кнопок ниже 👇
        )
# Задачи бота
async def startup_tasks():
    asyncio.create_task(manage_group_access_loop())

async def start_bot():
    await startup_tasks()
    await dp.start_polling()

def run_bot_polling():
    asyncio.run(start_bot())

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    if FLASK_ENV == "dev":
        # Локальный режим — только бот
        run_bot_polling()
    else:
        # Продакшен — Flask + бот в потоке
        threading.Thread(target=run_bot_polling, daemon=True).start()
        port = int(os.environ.get("PORT", 8080))
        app.run(host="0.0.0.0", port=port)