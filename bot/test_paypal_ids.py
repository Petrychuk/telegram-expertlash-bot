# test_paypal_ids.py
import json
import requests

from payment_config import (
    PAYPAL_CLIENT_ID,
    PAYPAL_CLIENT_SECRET,
    PAYPAL_API_BASE,
    PAYPAL_PLAN_ID,
    PAYPAL_RETURN_URL,
    PAYPAL_CANCEL_URL,
)

TELEGRAM_ID = 5379903145  # тестовый Telegram ID

def get_access_token():
    url = f"{PAYPAL_API_BASE}/v1/oauth2/token"
    headers = {"Accept": "application/json", "Accept-Language": "en_US"}
    data = {"grant_type": "client_credentials"}
    resp = requests.post(url, headers=headers, data=data, auth=(PAYPAL_CLIENT_ID, PAYPAL_CLIENT_SECRET), timeout=30)
    if resp.status_code != 200:
        raise RuntimeError(f"Auth failed: {resp.status_code} {resp.text}")
    return resp.json()["access_token"]

def create_subscription(access_token: str):
    url = f"{PAYPAL_API_BASE}/v1/billing/subscriptions"
    headers = {"Content-Type": "application/json", "Authorization": f"Bearer {access_token}"}
    payload = {
        "plan_id": PAYPAL_PLAN_ID,
        "custom_id": str(TELEGRAM_ID),  # мы так прокидываем telegram_id
        "application_context": {
            "brand_name": "Lash Course",
            "locale": "en-US",
            "shipping_preference": "NO_SHIPPING",
            "user_action": "SUBSCRIBE_NOW",
            "return_url": PAYPAL_RETURN_URL,
            "cancel_url": PAYPAL_CANCEL_URL,
        },
    }
    resp = requests.post(url, headers=headers, json=payload, timeout=30)
    if resp.status_code not in (201, 202):
        raise RuntimeError(f"Create subscription failed: {resp.status_code} {resp.text}")
    return resp.json()

def main():
    try:
        token = get_access_token()
        data = create_subscription(token)

        print("✅ Подписка создана (sandbox)")
        print("\n=== Короткая сводка ===")
        print("subscription.id:", data.get("id"))
        print("status:", data.get("status"))
        # ссылка для утверждения (approve)
        approval_url = next((l["href"] for l in data.get("links", []) if l.get("rel") == "approve"), None)
        print("approval_url:", approval_url)
        print("custom_id:", str(TELEGRAM_ID))

        print("\n=== Полный ответ PayPal (json) ===")
        print(json.dumps(data, indent=2, ensure_ascii=False))

        if not approval_url:
            print("\n⚠️  В ответе нет approve-ссылки. Проверь PAYPAL_PLAN_ID и статус плана (ACTIVE).")

    except Exception as e:
        print("❌ Ошибка:", e)

if __name__ == "__main__":
    main()
