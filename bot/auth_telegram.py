# auth_telegram.py
import hmac
import hashlib
import json
import time
import logging
from typing import Optional, Dict, Any
import jwt
from urllib.parse import unquote, parse_qs

from flask import Blueprint, request, jsonify, current_app, make_response
from database import get_db, get_user_by_telegram_id, create_user, get_active_subscription, UserRole, User

logger = logging.getLogger(__name__)
bp = Blueprint("auth_tg", __name__)

# ---------------------- Подпись initData ----------------------
def check_telegram_auth(init_data: str, bot_token: str) -> Optional[Dict[str, Any]]:
    """
    Проверяет подпись Telegram WebApp initData
    Исправленная версия с правильным порядком операций
    """
    if not init_data or not bot_token:
        logger.error("❌ Нет init_data или bot_token")
        return None

    try:
        # Добавляем отладочную информацию
        logger.debug(f"Raw init_data: {init_data}")
        logger.debug(f"BOT_TOKEN length: {len(bot_token)}")
        
        # Разбиваем строку на пары ключ=значение
        pairs = init_data.split('&')
        data_dict = {}
        received_hash = None
        
        for pair in pairs:
            if '=' in pair:
                key, value = pair.split('=', 1)
                if key == 'hash':
                    received_hash = value
                else:
                    data_dict[key] = value
        
        if not received_hash:
            logger.error("❌ initData не содержит hash")
            return None
        
        # Создаем строку для проверки (БЕЗ URL-декодирования!)
        # Сортируем пары по ключам
        sorted_pairs = sorted(data_dict.items())
        check_str = '\n'.join([f'{key}={value}' for key, value in sorted_pairs])
        
        logger.debug(f"Check string:\n{check_str}")
        
        # Создаем секретный ключ по алгоритму Telegram
        # 1. SHA256 от bot_token
        secret = hashlib.sha256(bot_token.encode()).digest()
        
        # 2. HMAC-SHA256("WebAppData", secret)
        secret_key = hmac.new("WebAppData".encode(), secret, hashlib.sha256).digest()
        
        # 3. HMAC-SHA256(check_str, secret_key)
        calculated_hash = hmac.new(secret_key, check_str.encode(), hashlib.sha256).hexdigest()
        
        logger.debug(f"Received Hash: {received_hash}")
        logger.debug(f"Calculated Hash: {calculated_hash}")
        
        # Сравниваем подписи
        if not hmac.compare_digest(calculated_hash, received_hash):
            logger.warning("❌ SIGNATURE VALIDATION FAILED")
            return None
        
        logger.info("✅ Подпись прошла проверку")
        
        # Теперь можем декодировать URL-encoded значения
        result = {}
        for key, value in data_dict.items():
            result[key] = unquote(value)
            
        return result
        
    except Exception as e:
        logger.error(f"Ошибка при проверке Telegram auth: {e}")
        return None

def validate_auth_date(data_dict: Dict[str, str], max_age: int = 86400) -> bool:
    """
    Проверяет, что initData не слишком старые
    max_age: максимальный возраст в секундах (по умолчанию 24 часа)
    """
    auth_date = data_dict.get('auth_date')
    if not auth_date:
        logger.warning("❌ auth_date отсутствует в initData")
        return False
    
    try:
        auth_timestamp = int(auth_date)
        current_timestamp = int(time.time())
        age = current_timestamp - auth_timestamp
        
        logger.debug(f"Auth date: {auth_timestamp}, Current: {current_timestamp}, Age: {age}s")
        
        if age > max_age:
            logger.warning(f"❌ initData слишком старые: {age}s > {max_age}s")
            return False
            
        if age < -300:  # Разрешаем небольшую разницу во времени (5 минут)
            logger.warning(f"❌ initData из будущего: {age}s")
            return False
            
        return True
        
    except ValueError:
        logger.error("❌ Некорректный формат auth_date")
        return False

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

    # Проверяем время жизни данных
    if not validate_auth_date(data):
        return jsonify({"error": "expired_auth_data"}), 401

    # Извлекаем пользователя
    try:
        user_json = data.get("user", "{}")
        logger.debug(f"User JSON: {user_json}")
        
        u = json.loads(user_json) if user_json else {}
        tg_id = int(u.get("id", 0))
        
        if not tg_id:
            logger.error("❌ Не удалось извлечь telegram ID")
            return jsonify({"error": "no_telegram_id"}), 400
            
        logger.info(f"User parsed: tg_id={tg_id}")
        
    except (json.JSONDecodeError, ValueError, TypeError) as e:
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
        
    except Exception as e:
        logger.error(f"Ошибка в базе данных: {e}")
        return jsonify({"error": "database_error"}), 500
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
    except (jwt.ExpiredSignatureError, jwt.InvalidTokenError) as e:
        logger.warning(f"Invalid token: {e}")
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