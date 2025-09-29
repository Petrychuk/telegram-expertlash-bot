# auth_telegram.py
import hmac
import hashlib
import json
import time
import logging
from typing import Optional, Dict, Any
import jwt
from urllib.parse import unquote

from flask import Blueprint, request, jsonify, current_app, make_response
from database import get_db, get_user_by_telegram_id, create_user, get_active_subscription, UserRole, User

logger = logging.getLogger(__name__)
bp = Blueprint("auth_tg", __name__)

def check_telegram_auth(init_data: str, bot_token: str) -> Optional[Dict[str, Any]]:
   
    if not init_data or not bot_token:
        return None

    try:
        # Разбираем строку на пары ключ=значение
        data_pairs = [x.split('=', 1) for x in init_data.split('&')]
        data_dict = dict(data_pairs)
    except ValueError:
        return None

    # Извлекаем хэш для проверки
    received_hash = data_dict.pop("hash", None)
    if not received_hash:
        return None

    # Составляем проверочную строку
    check_pairs = [f"{key}={value}" for key, value in data_dict.items()]
    check_pairs.sort()
    check_str = "\n".join(check_pairs)

    # Секретный ключ генерируется через HMAC, а не простым SHA256.
    secret_key = hmac.new("WebAppData".encode(), bot_token.encode(), hashlib.sha256).digest()
    
    # Хэшируем проверочную строку с этим секретным ключом
    calculated_hash = hmac.new(secret_key, check_str.encode(), hashlib.sha256).hexdigest()

    if not hmac.compare_digest(calculated_hash, received_hash):
        logger.warning("SIGNATURE VALIDATION FAILED. This should not happen with the correct secret key logic.")
        return None

    # Успех! Раскодируем значения для дальнейшего использования.
    safe_data = {key: unquote(value) for key, value in data_dict.items()}
    return safe_data

@bp.post("/api/auth/telegram")
def auth_telegram():
    body = request.get_json(silent=True) or {}
    init_data = body.get("init_data", "")
    if not init_data:
        return jsonify({"error": "no_init_data"}), 400

    bot_token = current_app.config.get("BOT_TOKEN")
    jwt_secret = current_app.config.get("JWT_SECRET")

    data = check_telegram_auth(init_data, bot_token)
    if not data:
        return jsonify({"error": "bad_signature"}), 401

    logger.info("✅✅✅ SIGNATURE IS OK! WE DID IT! ✅✅✅")

    try:
        u = json.loads(data.get("user", "{}")) or {}
        tg_id = int(u.get("id"))
    except Exception:
        return jsonify({"error": "malformed_user"}), 400

    db = next(get_db())
    try:
        user = get_user_by_telegram_id(db, tg_id)
        if not user:
            user = create_user(db, tg_id, username=u.get("username"), first_name=u.get("first_name"), last_name=u.get("last_name"))
        
        sub = get_active_subscription(db, user.id)
        has_access = (user.role == UserRole.admin) or (sub is not None)
        
        if not has_access:
            return jsonify({"error": "no_subscription"}), 403

        now = int(time.time())
        payload = {"sub": user.id, "iat": now, "exp": now + 60 * 60 * 24 * 7, "role": user.role.value}
        token = jwt.encode(payload, jwt_secret, algorithm="HS256")

        response = make_response(jsonify({"status": "success"}))
        response.set_cookie(
            'auth_token', value=token, max_age=60 * 60 * 24 * 7,
            path='/', httponly=True, samesite='Lax'
         )
        return response
    finally:
        db.close()

@bp.get("/api/auth/me")
def get_current_user():
    jwt_secret = current_app.config.get("JWT_SECRET")
    token = request.cookies.get('auth_token')
    if not token:
        return jsonify({"error": "no_token"}), 401

    try:
        payload = jwt.decode(token, jwt_secret, algorithms=["HS256"])
        user_id = int(payload["sub"])
    except Exception:
        return jsonify({"error": "bad_token"}), 401

    db = next(get_db())
    try:
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            return jsonify({"error": "user_not_found"}), 404

        db.refresh(user)
        sub = get_active_subscription(db, user.id)
        has_access = (user.role == UserRole.admin) or (sub is not None)

        return jsonify({
            "user": {
                "id": user.id, "tg_id": user.telegram_id, "role": user.role.value,
                "username": user.username, "first_name": user.first_name,
                "last_name": user.last_name, "hasSubscription": has_access,
            }
        })
    finally:
        db.close()
