import os
import time
import threading
import logging
import asyncio
from webhook import app                 # Flask-приложение
from main import run_bot_polling        # запуск aiogram
from tasks import run_all_jobs          

logger = logging.getLogger(__name__)

def _start_bot():
    threading.Thread(target=run_bot_polling, daemon=True).start()

def _start_scheduler():
    """
    Внутренний «крон». Запускает все джобы из tasks.py по интервалу.
    Управляется переменными окружения:
      - CRON_ENABLED=true|false
      - CRON_INTERVAL_MIN=60 (минуты для теста)
      - CRON_INTERVAL_PROD=1d  (игнорируется здесь; оставлена для совместимости)
    """
    enabled = os.getenv("CRON_ENABLED", "true").lower() in ("1", "true", "yes")
    if not enabled:
        logger.info("Scheduler disabled (CRON_ENABLED=false)")
        return

    interval_min = int(os.getenv("CRON_INTERVAL_MIN", "60"))  # по умолчанию раз в час

    def loop():
        logger.info(f"Scheduler started, interval={interval_min}min")
        while True:
            try:
                asyncio.run(run_all_jobs())
            except Exception as e:
                logger.exception(f"Scheduler run_all_jobs error: {e}")
            time.sleep(interval_min * 60)

    threading.Thread(target=loop, daemon=True).start()
# поднимаем всё
_start_bot()
_start_scheduler()


