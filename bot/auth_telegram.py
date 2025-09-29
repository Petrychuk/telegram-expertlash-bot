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

# ---------------------- Подпись initData ----------------------
def check_telegram_auth(init_data: str, bot_token: str) -> Optional[Dict[str, Any]]:
   
    if not init_data or not bot_token:
        logger.error("❌ Нет init_data или bot_token")
        return None

    try:
        data_pairs = [x.split("=", 1) for x in init_data.split("&")]
        data_dict = dict(data_pairs)
    except Exception as e:
        logger.error(f"Ошибка парсинга initData: {e}")
        return None

    received_hash = data_dict.pop("hash", None)
    if not received_hash:
        logger.error("❌ initData не содержит hash")
        return None

    # Собираем строку для проверки
    check_pairs = [f"{k}={v}" for k, v in data_dict.items()]
    check_pairs.sort()
    check_str = "\n".join(check_pairs)

    # 1. sha256(bot_token)
    secret = hashlib.sha256(bot_token.encode()).digest()

    # 2. hmac("WebAppData", secret)
    secret_key = hmac.new("WebAppData".encode(), secret, hashlib.sha256).digest()

    # 3. hmac(check_str, secret_key)
    calculated_hash = hmac.new(secret_key, check_str.encode(), hashlib.sha256).hexdigest()

    if not hmac.compare_digest(calculated_hash, received_hash):
        logger.warning("❌ SIGNATURE VALIDATION FAILED")
        logger.debug(f"Check string:\n{check_str}")
        logger.debug(f"Received Hash: {received_hash}")
        logger.debug(f"Calculated Hash: {calculated_hash}")
        return None

    logger.info("✅ Подпись прошла проверку")
    return {k: unquote(v) for k, v in data_dict.items()}

# ---------------------- /api/auth/telegram ----------------------
@bp.post("/api/auth/telegram")
def auth_telegram():
    logger.info("--- START /api/auth/telegram ---")

    body = request.get_json(silent=True) or {}
    init_data = body.get("init_data", "")
    if not init_data:
        logger.error("❌ init_data отсутствует в body")
        return jsonify({"error": "no_init_data"}), 400

    bot_token = current_app.config.get("BOT_TOKEN")
    jwt_secret = current_app.config.get("JWT_SECRET")

    if not bot_token or not jwt_secret:
        logger.critical("CRITICAL: BOT_TOKEN или JWT_SECRET не загружен в конфиг")
        return jsonify({"error": "server_misconfigured"}), 500

    # Проверяем подпись
    logger.info("Проверяем подпись initData...")
    data = check_telegram_auth(init_data, bot_token)
    if not data:
        return jsonify({"error": "bad_signature"}), 401

    # Извлекаем пользователя
    try:
        u = json.loads(data.get("user", "{}")) or {}
        tg_id = int(u.get("id"))
        logger.info(f"User parsed: tg_id={tg_id}")
    except Exception as e:
        logger.error(f"Ошибка парсинга user: {e}")
        return jsonify({"error": "malformed_user"}), 400

    db = next(get_db())
    try:
        user = get_user_by_telegram_id(db, tg_id)
        if not user:
            user = create_user(
                db,
                tg_id,
                username=u.get("username"),
                first_name=u.get("first_name"),
                last_name=u.get("last_name")
            )
            logger.info(f"Создан новый пользователь id={user.id}")

        sub = get_active_subscription(db, user.id)
        has_access = (user.role == UserRole.admin) or (sub is not None)

        if not has_access:
            logger.warning(f"Нет подписки: user_id={user.id}")
            return jsonify({"error": "no_subscription"}), 403

        # Создаём JWT
        now = int(time.time())
        payload = {
            "sub": user.id,
            "iat": now,
            "exp": now + 60 * 60 * 24 * 7,
            "role": user.role.value,
        }
        token = jwt.encode(payload, jwt_secret, algorithm="HS256")

        response = make_response(jsonify({"status": "success"}))
        response.set_cookie(
            "auth_token",
            value=token,
            max_age=60 * 60 * 24 * 7,
            path="/",
            httponly=True,
            samesite="Lax",
        )
        logger.info(f"✅ Успешная авторизация: user_id={user.id}")
        return response
    finally:
        db.close()

# ---------------------- /api/auth/me ----------------------
@bp.get("/api/auth/me")
def get_current_user():
    jwt_secret = current_app.config.get("JWT_SECRET")
    token = request.cookies.get("auth_token")
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
                "id": user.id,
                "tg_id": user.telegram_id,
                "role": user.role.value,
                "username": user.username,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "hasSubscription": has_access,
            }
        })
    finally:
        db.close()
