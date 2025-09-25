# tests/smoke_test.py 

import os
import sys
import requests
# --- Настройка путей для импорта ---
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(ROOT_DIR, ".env"))
except ImportError:
    print("⚠️  dotenv не установлен, тесты могут не найти переменные окружения.")

def check_env_vars():
    print("\n--- 1. Проверка переменных окружения ---")
    required = ["BOT_TOKEN", "JWT_SECRET", "DB_USER", "DB_PASSWORD", "DB_HOST", "DB_PORT", "DB_NAME"]
    all_ok = True
    for var in required:
        if os.getenv(var):
            print(f"✅ {var} - OK")
        else:
            print(f"❌ {var} - НЕ НАЙДЕНО!")
            all_ok = False
    return all_ok

def check_file_structure():
    print("\n--- 2. Проверка структуры файлов ---")
    required = ["main.py", "webhook.py", "database.py", "auth_telegram.py", "payment_service.py", "telegram_service.py"]
    all_ok = True
    for f in required:
        path = os.path.join(ROOT_DIR, f)
        if os.path.exists(path):
            print(f"✅ {f} - OK")
        else:
            print(f"❌ {f} - НЕ НАЙДЕН!")
            all_ok = False
    return all_ok

def check_database_connection():
    print("\n--- 3. Проверка подключения к БД ---")
    try:
        from database import get_db
        db = next(get_db())
        db.execute("SELECT 1")
        db.close()
        print("✅ Подключение к БД - OK")
        return True
    except Exception as e:
        print(f"❌ Ошибка подключения к БД: {e}")
        return False

def check_api_health():
    print("\n--- 4. Проверка доступности API (health check) ---")
    url = "http://127.0.0.1:8080/health"
    try:
        r = requests.get(url, timeout=5 )
        if r.status_code == 200:
            print(f"✅ {url} - OK (статус 200)")
            return True
        else:
            print(f"❌ {url} - Ошибка (статус {r.status_code})")
            return False
    except requests.RequestException as e:
        print(f"❌ Не удалось подключиться к {url}. Убедитесь, что бэкенд запущен.")
        return False

def main():
    print("🚀 Запуск SMOKE-теста системы...")
    results = {
        "Переменные окружения": check_env_vars(),
        "Структура файлов": check_file_structure(),
        "Подключение к БД": check_database_connection(),
        "Health Check API": check_api_health(),
    }
    
    print("\n" + "="*30)
    print("РЕЗУЛЬТАТЫ:")
    print("="*30)
    
    all_passed = all(results.values())
    for name, result in results.items():
        status = "✅ ПРОЙДЕН" if result else "❌ НЕ ПРОЙДЕН"
        print(f"{status} - {name}")
        
    if all_passed:
        print("\n🎉 Все базовые проверки пройдены! Система готова к работе.")
    else:
        print("\n⚠️  Обнаружены критические проблемы. Пожалуйста, исправьте ошибки выше.")

if __name__ == "__main__":
    main()
