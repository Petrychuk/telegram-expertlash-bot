# auth_telegram.py
from __future__ import annotations

import hmac
import hashlib
import json
import time
from typing import Optional, Dict, Any

import jwt
from urllib.parse import parse_qsl
from flask import Blueprint, request, jsonify, current_app

from database import get_db, get_user_by_telegram_id, create_user, get_active_subscription

bp = Blueprint("auth_tg", __name__)

def check_telegram_auth(init_data: str, bot_token: str) -> Optional[Dict[str, Any]]:
    """
    Проверка подписи Telegram WebApp initData.
    Возвращает словарь данных при успехе, иначе None.
    """
    if not init_data or not bot_token:
        return None

    data = dict(parse_qsl(init_data, keep_blank_values=True))
    recv_hash = data.pop("hash", None)
    if not recv_hash:
        return None

    check_str = "\n".join(f"{k}={data[k]}" for k in sorted(data.keys()))
    secret = hashlib.sha256(bot_token.encode("utf-8")).digest()
    calc_hash = hmac.new(secret, check_str.encode("utf-8"), hashlib.sha256).hexdigest()

    # постоянное сравнение (без утечек по времени)
    if not hmac.compare_digest(calc_hash, recv_hash):
        return None

    return data


@bp.post("/api/auth/telegram")
def auth_telegram():
    """
    Принимает init_data из Telegram WebApp.
    1) Валидирует подпись.
    2) Создаёт пользователя при первом входе.
    3) Проверяет, что у пользователя есть активная подписка.
    4) Возвращает JWT на 7 дней.
    """
    body = request.get_json(silent=True) or {}
    init_data = body.get("init_data", "")
    if not init_data:
        return jsonify({"error": "no_init_data"}), 400

    bot_token = current_app.config.get("BOT_TOKEN")
    jwt_secret = current_app.config.get("JWT_SECRET")
    if not bot_token or not jwt_secret:
        return jsonify({"error": "server_misconfigured"}), 500

    data = check_telegram_auth(init_data, bot_token)
    if not data:
        return jsonify({"error": "bad_signature"}), 401

    # user — JSON-строка внутри initData
    try:
        u = json.loads(data.get("user", "{}")) or {}
        tg_id = int(u.get("id"))
    except Exception:
        return jsonify({"error": "malformed_user"}), 400

    username = u.get("username")
    first_name = u.get("first_name")
    last_name = u.get("last_name")

    db = next(get_db())
    try:
        user = get_user_by_telegram_id(db, tg_id)
        if not user:
            user = create_user(db, tg_id, username=username, first_name=first_name, last_name=last_name)

        sub = get_active_subscription(db, tg_id)
        if not sub:
            return jsonify({"error": "no_subscription"}), 403
    finally:
        db.close()

    now = int(time.time())
    payload = {
        "sub": str(tg_id),
        "iat": now,
        "exp": now + 60 * 60 * 24 * 7,  # 7 дней
        "scope": "learner",
    }
    token = jwt.encode(payload, jwt_secret, algorithm="HS256")
    return jsonify({"token": token})


@bp.get("/api/auth/test")
def auth_test():
    """
    Тестовая выдача JWT на 1 час, чтобы быстро проверить интеграцию на клиенте.
    """
    jwt_secret = current_app.config.get("JWT_SECRET")
    if not jwt_secret:
        return jsonify({"error": "server_misconfigured"}), 500

    now = int(time.time())
    payload = {"sub": "test", "iat": now, "exp": now + 3600, "scope": "test"}
    token = jwt.encode(payload, jwt_secret, algorithm="HS256")
    return jsonify({"token": token})
