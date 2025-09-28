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

# Устанавливаем более детальный уровень логирования для этого файла
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG) 

bp = Blueprint("auth_tg", __name__)

def check_telegram_auth(init_data: str, bot_token: str) -> Optional[Dict[str, Any]]:
    """
    Проверка подписи initData для Telegram Mini App.
    Работает с 'signature=' (новый формат).
    """
    if not init_data or not bot_token:
        return None

    # 🔑 Сначала раскодируем, если строка закодирована как query
    init_data = unquote(init_data)
    logger.debug(f"Raw init_data after unquote (first 200 chars): {init_data[:200]}")

    try:
        data_pairs = [x.split("=", 1) for x in init_data.split("&")]
    except ValueError:
        logger.error("❌ Ошибка парсинга initData")
        return None

    data_dict = dict(data_pairs)
    received_signature = data_dict.get("signature")
    if not received_signature:
        logger.error("❌ initData не содержит signature")
        return None

    # Берём все пары кроме signature
    check_pairs = [f"{k}={v}" for k, v in data_pairs if k != "signature"]
    check_pairs.sort()
    check_str = "\n".join(check_pairs)

    # 👇 Правильный ключ для Mini App
    secret_key = hmac.new(b"WebAppData", bot_token.encode("utf-8"), hashlib.sha256).digest()
    calculated_signature = hmac.new(secret_key, check_str.encode("utf-8"), hashlib.sha256).hexdigest()

    if not hmac.compare_digest(calculated_signature, received_signature):
        logger.warning("❌ SIGNATURE VALIDATION FAILED")
        logger.debug(f"Check string:\n{check_str}")
        logger.debug(f"Received signature: {received_signature}")
        logger.debug(f"Calculated signature: {calculated_signature}")
        return None

    logger.info("✅ initData signature validated successfully")
    return {k: unquote(v) for k, v in data_dict.items()}

@bp.post("/api/auth/telegram")
def auth_telegram():
    logger.info("--- START /api/auth/telegram ---")
    body = request.get_json(silent=True) or {}
    init_data = body.get("init_data", "")
    if not init_data:
        logger.error("Auth failed: 'init_data' field is missing.")
        return jsonify({"error": "no_init_data"}), 400

    # --- ЛОГИРОВАНИЕ СЕКРЕТОВ ---
    bot_token = current_app.config.get("BOT_TOKEN")
    jwt_secret = current_app.config.get("JWT_SECRET")

    if not bot_token:
        logger.critical("CRITICAL: BOT_TOKEN is NOT loaded in Flask config!")
    else:
        logger.info(f"BOT_TOKEN loaded, preview: {bot_token[:4]}...{bot_token[-4:]}")

    if not jwt_secret:
        logger.critical("CRITICAL: JWT_SECRET is NOT loaded in Flask config!")
    else:
        logger.info(f"JWT_SECRET loaded, preview: {jwt_secret[:4]}...")
    
    if not bot_token or not jwt_secret:
        return jsonify({"error": "server_misconfigured"}), 500

    # --- ПРОВЕРКА ПОДПИСИ ---
    logger.info("Attempting to validate signature...")
    data = check_telegram_auth(init_data, bot_token)
    if not data:
        logger.error("Signature validation returned None. Sending 401 bad_signature.")
        return jsonify({"error": "bad_signature"}), 401

    logger.info("✅ Signature is OK! Proceeding...")

    # --- ПРОВЕРКА ПОЛЬЗОВАТЕЛЯ И ПОДПИСКИ ---
    try:
        u = json.loads(data.get("user", "{}")) or {}
        tg_id = int(u.get("id"))
        logger.info(f"User data parsed, tg_id={tg_id}")
    except Exception as e:
        logger.error(f"Failed to parse user data from initData: {e}")
        return jsonify({"error": "malformed_user"}), 400

    db = next(get_db())
    try:
        user = get_user_by_telegram_id(db, tg_id)
        if not user:
            user = create_user(db, tg_id, username=u.get("username"), first_name=u.get("first_name"), last_name=u.get("last_name"))
            logger.info(f"Created new user with internal_id={user.id}")
        
        sub = get_active_subscription(db, user.id)
        has_access = (user.role == UserRole.admin) or (sub is not None)
        logger.info(f"Access check for user_id={user.id}: has_access={has_access}")
        
        if not has_access:
            logger.warning(f"Access DENIED for user_id={user.id}. No active subscription.")
            return jsonify({"error": "no_subscription"}), 403

        # --- СОЗДАНИЕ JWT ---
        now = int(time.time())
        payload = {"sub": user.id, "iat": now, "exp": now + 60 * 60 * 24 * 7, "role": user.role.value}
        token = jwt.encode(payload, jwt_secret, algorithm="HS256")
        logger.info(f"JWT created for user_id={user.id}")

        response = make_response(jsonify({"status": "success"}))
        response.set_cookie(
            'auth_token', value=token, max_age=60 * 60 * 24 * 7,
            path='/', httponly=True, samesite='Lax'
         )
        logger.info("Cookie 'auth_token' set. Sending response.")
        logger.info("--- END /api/auth/telegram ---")
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
    except (jwt.ExpiredSignatureError, jwt.InvalidTokenError):
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
