# tests/test_02_auth.py

import jwt
import time
import json
from unittest.mock import patch

from auth_telegram import check_telegram_auth
from database import create_user, create_subscription

# --- Тестовые данные ---
FAKE_BOT_TOKEN = "12345:ABC-test-token"
TEST_USER_ID = 987654321
JWT_SECRET = "test-secret"

def generate_fake_init_data(user_data: dict, bot_token: str) -> str:
    """Генерирует валидную строку initData для теста."""
    import hmac, hashlib
    auth_date = int(time.time())
    data_to_sign = {
        "auth_date": str(auth_date),
        "query_id": "fake_query_id",
        "user": json.dumps(user_data, sort_keys=True, separators=(',', ':'))
    }
    check_str = "\n".join(f"{k}={v}" for k, v in sorted(data_to_sign.items()))
    secret_key = hmac.new("WebAppData".encode(), bot_token.encode(), hashlib.sha256).digest()
    h = hmac.new(secret_key, check_str.encode(), hashlib.sha256)
    data_to_sign["hash"] = h.hexdigest()
    return "&".join([f"{k}={v}" for k, v in data_to_sign.items()])

def test_check_telegram_auth_valid():
    """Unit-тест: Проверяет, что валидная подпись проходит проверку."""
    user_data = {"id": TEST_USER_ID, "username": "test"}
    init_data = generate_fake_init_data(user_data, FAKE_BOT_TOKEN)
    
    parsed_data = check_telegram_auth(init_data, FAKE_BOT_TOKEN)
    assert parsed_data is not None
    assert json.loads(parsed_data['user'])['id'] == TEST_USER_ID

def test_check_telegram_auth_invalid():
    """Unit-тест: Проверяет, что невалидная подпись не проходит проверку."""
    user_data = {"id": TEST_USER_ID, "username": "test"}
    init_data = generate_fake_init_data(user_data, FAKE_BOT_TOKEN)
    
    # Искажаем токен
    parsed_data = check_telegram_auth(init_data, "wrong-token")
    assert parsed_data is None

def test_auth_telegram_endpoint_no_subscription(client, db_session):
    """Integration-тест: /api/auth/telegram должен вернуть 403, если нет подписки."""
    user_data = {"id": TEST_USER_ID, "username": "test"}
    init_data = generate_fake_init_data(user_data, FAKE_BOT_TOKEN)
    
    response = client.post("/api/auth/telegram", json={"init_data": init_data})
    
    assert response.status_code == 403
    assert response.json['error'] == "no_subscription"

def test_auth_telegram_endpoint_with_subscription(client, db_session):
    """Integration-тест: /api/auth/telegram должен вернуть 200 и токен, если есть подписка."""
    from database import activate_subscription
    
    # Создаем пользователя и активную подписку
    user = create_user(db_session, telegram_id=TEST_USER_ID)
    create_subscription(db_session, user_id=user.id, subscription_id="sub_123", order_id="ord_123", payment_system="test")
    activate_subscription(db_session, user_id=user.id, order_id="ord_123")

    user_data = {"id": TEST_USER_ID, "username": "test"}
    init_data = generate_fake_init_data(user_data, FAKE_BOT_TOKEN)
    
    response = client.post("/api/auth/telegram", json={"init_data": init_data})
    
    assert response.status_code == 200
    assert "token" in response.json
    assert "profile" in response.json
    assert response.json['profile']['hasSubscription'] is True
    
    # Проверяем, что cookie установлен
    assert 'auth_token' in response.headers['Set-Cookie']

def test_auth_me_endpoint(client, db_session):
    """Integration-тест: /api/auth/me должен вернуть профиль по валидному токену."""
    user = create_user(db_session, telegram_id=TEST_USER_ID)
    
    # Создаем токен вручную
    payload = {"sub": user.id, "exp": int(time.time()) + 3600}
    token = jwt.encode(payload, JWT_SECRET, algorithm="HS256")
    
    # Устанавливаем cookie и делаем запрос
    client.set_cookie('auth_token', token)
    response = client.get("/api/auth/me")
    
    assert response.status_code == 200
    assert response.json['user']['id'] == user.id
