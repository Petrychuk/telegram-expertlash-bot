# server.py
import threading
from webhook import app               # Flask-приложение
from main import run_bot_polling      # функция, которая запускает aiogram

# поднимаем телеграм-бота в отдельном потоке
threading.Thread(target=run_bot_polling, daemon=True).start()

