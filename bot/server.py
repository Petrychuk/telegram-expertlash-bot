# server.py
import os, threading
from webhook import app               # Flask-приложение
from main import run_bot_polling      # функция, которая запускает aiogram

# поднимаем телеграм-бота в отдельном потоке
threading.Thread(target=run_bot_polling, daemon=True).start()

if os.getenv("RUN_JOBS_ON_START", "0") == "1":
    from tasks import run_all_sync
    threading.Thread(target=run_all_sync, daemon=True).start()

