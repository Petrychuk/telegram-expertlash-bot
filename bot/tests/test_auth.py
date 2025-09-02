import requests
import json

URL = "http://127.0.0.1:8080/api/auth/telegram"

# ⚠️ пока что фейковое значение init_data — для проверки доступности
payload = {
    "init_data": "test"
}

try:
    r = requests.post(URL, json=payload)
    print("Status code:", r.status_code)
    print("Response:", json.dumps(r.json(), indent=2, ensure_ascii=False))
except Exception as e:
    print("Ошибка запроса:", e)
