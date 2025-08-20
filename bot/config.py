import os
# --- НАСТРОЙКИ БОТА ---
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_FALLBACK_ID = int(os.getenv("ADMIN_FALLBACK_ID", "0")) or None
VIDEO_PENDING_FILE_ID = os.getenv("VIDEO_PENDING_FILE_ID")
VIDEO_PRESENTATION_FILE_ID = os.getenv("VIDEO_PRESENTATION_FILE_ID")
VIDEO_REVIEWS = os.getenv("VIDEO_REVIEWS")

# --- ВИДЕО FILE_ID (ЗАМЕНИТЕ НА РЕАЛЬНЫЕ ПОСЛЕ ЗАГРУЗКИ ВИДЕО) ---
# Для тестирования используем None, чтобы отправлять текстовые заглушки
# VIDEO_REVIEWS = {
#     "review_1": None,  # Замените на реальные file_id после загрузки видео
#     "review_2": None,
#     "review_3": None,
#     "review_4": None,
#     "review_5": None
# }

