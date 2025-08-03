import os


# --- НАСТРОЙКИ БОТА ---
BOT_TOKEN = os.getenv("BOT_TOKEN")

# --- ВИДЕО FILE_ID (ЗАМЕНИТЕ НА РЕАЛЬНЫЕ ПОСЛЕ ЗАГРУЗКИ ВИДЕО) ---
# Для тестирования используем None, чтобы отправлять текстовые заглушки
VIDEO_PRESENTATION_FILE_ID = None  # Замените на реальный file_id
VIDEO_REVIEWS = {
    "review_1": None,  # Замените на реальные file_id после загрузки видео
    "review_2": None,
    "review_3": None,
    "review_4": None,
    "review_5": None
}
