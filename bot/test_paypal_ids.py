import os
import requests
from dotenv import load_dotenv

load_dotenv()

PAYPAL_CLIENT_ID = os.getenv("PAYPAL_CLIENT_ID")
PAYPAL_SECRET = os.getenv("PAYPAL_SECRET")
BASE_URL = "https://api-m.sandbox.paypal.com"  # sandbox-режим

# Получаем access_token
auth_resp = requests.post(
    f"{BASE_URL}/v1/oauth2/token",
    auth=(PAYPAL_CLIENT_ID, PAYPAL_SECRET),
    data={"grant_type": "client_credentials"}
)

if auth_resp.status_code != 200:
    print("Ошибка авторизации:", auth_resp.text)
    exit()

access_token = auth_resp.json()["access_token"]

telegram_id = 5379903145  # тестовый Telegram ID

# Создаём тестовый заказ
order_data = {
    "intent": "CAPTURE",
    "purchase_units": [{
        "amount": {"currency_code": "EUR", "value": "5.00"},
        "custom_id": str(telegram_id)
    }]
}

order_resp = requests.post(
    f"{BASE_URL}/v2/checkout/orders",
    headers={
        "Content-Type": "application/json",
        "Authorization": f"Bearer {access_token}"
    },
    json=order_data
)

if order_resp.status_code != 201:
    print("Ошибка создания заказа:", order_resp.text)
    exit()

order_info = order_resp.json()

print("=== Полный ответ PayPal ===")
print(order_info)

print("\nOrder ID:", order_info.get("id"))
print("Custom ID:", order_info["purchase_units"][0].get("custom_id"))
