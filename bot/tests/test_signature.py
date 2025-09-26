# test_signature.py
import hmac
import hashlib
from urllib.parse import parse_qsl

# --- ВСТАВЬТЕ ВАШИ ДАННЫЕ СЮДА ---

# 1. Возьмите эту строку из логов Railway (из поля BACKEND initData)
init_data_string = "query_id=AGpzqpAAgAAAKnOqkBU9vre&user=%7B%22id%22%3A5379903145%2C%22first_name%22%3A%22Nataliia%22%2C%22last_name%22%3A%22Petrychuk%22%2C%22language_code%22%3A%22en%22%2C%22allows_write_to_pm%22%3Atrue%2C%22photo_url%22%3A%22https%3A%5C%2F%5C%2Ft.me%5C%2Fi%5C%2Fuserpic%5C%2F320%5C%2FHh4MUrTNVLYvZh_CWT3LXEyLELP6UVFSGMzm5zjFNzpYE9Z66zc7CXNsJmonOUT8.svg%22%7D&auth_date=1758868248&signature=ULJowVCYuPHAZrEPy7aMbceWbO-kd8x4a6-zcrsBhG0hTKftS3ydLYn3sUSfc9QCKIK1vrn1uEdt92NIssS_Cg&hash=ed7b032a8120ecc20fb7492194ed0cf3c847bd46e7b924fbea2ddac75e35cc36"

# 2. Возьмите ваш ПОЛНЫЙ токен бота у @BotFather
bot_token = "7877937866:AAFTkwfC510tx2nLmacd1jazRBYGHiGatko"

# --- КОНЕЦ ВАШИХ ДАННЫХ ---


# Функция проверки, скопированная 1 в 1 с вашего бэкенда
def check_telegram_auth(init_data: str, token: str ):
    print("--- Starting Verification ---")
    try:
        data = dict(parse_qsl(init_data, keep_blank_values=True))
        print(f"1. Parsed data: {len(data)} fields")

        # Извлекаем hash и signature
        received_hash = data.pop("hash", None)
        data.pop("signature", None) # Удаляем signature, как и договаривались
        
        if not received_hash:
            print("Error: 'hash' field not found in initData.")
            return

        print(f"2. Received Hash: {received_hash}")
        
        # Составляем проверочную строку
        sorted_keys = sorted(data.keys())
        print(f"3. Keys for check string (sorted): {sorted_keys}")
        
        check_str = "\n".join(f"{k}={data[k]}" for k in sorted_keys)
        print(f"4. Check String:\n---\n{check_str}\n---")

        # Хэшируем токен
        secret_key = hashlib.sha256(token.encode("utf-8")).digest()
        print("5. Secret key generated from bot token.")

        # Вычисляем наш хэш
        calculated_hash = hmac.new(secret_key, check_str.encode("utf-8"), hashlib.sha256).hexdigest()
        print(f"6. Calculated Hash: {calculated_hash}")

        # Сравниваем
        if hmac.compare_digest(calculated_hash, received_hash):
            print("\n✅ SUCCESS: Hashes match! The signature is valid.")
        else:
            print("\n❌ FAILURE: Hashes DO NOT match! The signature is invalid.")

    except Exception as e:
        print(f"\nAn error occurred: {e}")

# Запускаем проверку
check_telegram_auth(init_data_string, bot_token)
