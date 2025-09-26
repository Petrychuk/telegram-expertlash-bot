# auth_telegram.py
import hmac, hashlib, json, time, logging 
from typing import Optional, Dict, Any
import jwt
from urllib.parse import parse_qsl
from flask import Blueprint, request, jsonify, current_app, make_response
from database import get_db, get_user_by_telegram_id, create_user, get_active_subscription, UserRole, User
from urllib.parse import unquote

logger = logging.getLogger(__name__)
bp = Blueprint("auth_tg", __name__)

def check_telegram_auth(init_data: str, bot_token: str) -> Optional[Dict[str, Any]]:
    """
    Проверяет подлинность данных, полученных от Telegram WebApp.
    Эта версия корректно работает с URL-кодированными значениями.
    """
    if not init_data or not bot_token:
        return None

    # Разбираем строку на пары ключ=значение
    try:
        # Важно: мы не используем parse_qsl, чтобы значения не раскодировались автоматически
        data_pairs = [x.split('=', 1) for x in init_data.split('&')]
    except ValueError:
        return None

    # Ищем и извлекаем hash
    try:
        data_dict = dict(data_pairs)
        received_hash = data_dict.pop("hash", None)
        if not received_hash:
            return None
    except (ValueError, KeyError):
        return None

    # Составляем проверочную строку из ОРИГИНАЛЬНЫХ пар, исключая hash
    check_pairs = [f"{key}={value}" for key, value in data_pairs if key != "hash"]
    check_pairs.sort() # Сортируем по ключу
    check_str = "\n".join(check_pairs)

    # Хэшируем и сравниваем
    secret = hashlib.sha256(bot_token.encode("utf-8")).digest()
    calculated_hash = hmac.new(secret, check_str.encode("utf-8"), hashlib.sha256).hexdigest()

    if not hmac.compare_digest(calculated_hash, received_hash):
        # --- ОТЛАДКА, ЕСЛИ ВСЕ ЕЩЕ НЕ РАБОТАЕТ ---
        logger.warning("Auth failed: bad signature (FINAL VERSION).")
        logger.debug(f"Check String Used:\n---\n{check_str}\n---")
        logger.debug(f"Received Hash:   {received_hash}")
        logger.debug(f"Calculated Hash: {calculated_hash}")
        # -----------------------------------------
        return None

    # Если проверка прошла, теперь мы можем безопасно раскодировать значения
    # для дальнейшего использования (например, для получения user_id)
    safe_data = {}
    for key, value in data_dict.items():
        safe_data[key] = unquote(value)
        
    return safe_data

@bp.post("/api/auth/telegram")
def auth_telegram():
    body = request.get_json(silent=True) or {}
    init_data = body.get("init_data", "")
    if not init_data:
        return jsonify({"error": "no_init_data"}), 400

    bot_token = current_app.config.get("BOT_TOKEN")
    jwt_secret = current_app.config.get("JWT_SECRET")
    if not bot_token or not jwt_secret:
        return jsonify({"error": "server_misconfigured"}), 500

    # Вызываем нашу новую, правильную функцию
    data = check_telegram_auth(init_data, bot_token)
    if not data:
        return jsonify({"error": "bad_signature"}), 401

    logger.info("Signature is OK! Proceeding with user check.")

    try:
        # Теперь 'user' в `data` - это раскодированная строка
        u = json.loads(data.get("user", "{}")) or {}
        tg_id = int(u.get("id"))
        logger.info(f"Auth attempt for tg_id={tg_id}")
    except Exception:
        logger.error("Auth failed: malformed user data after unquote.")
        return jsonify({"error": "malformed_user"}), 400

    db = next(get_db())
    try:
        user = get_user_by_telegram_id(db, tg_id)
        if not user:
            user = create_user(db, tg_id, username=u.get("username"), first_name=u.get("first_name"), last_name=u.get("last_name"))
        
        sub = get_active_subscription(db, user.id)
        is_admin = user.role == UserRole.admin
        has_access = is_admin or (sub is not None)
        
        if not has_access:
            logger.warning(f"Access denied for user_id={user.id} (tg_id={tg_id}): no active subscription.")
            return jsonify({"error": "no_subscription"}), 403

        now = int(time.time())
        payload = {"sub": user.id, "iat": now, "exp": now + 60 * 60 * 24 * 7, "role": user.role.value}
        token = jwt.encode(payload, jwt_secret, algorithm="HS256")

        profile_data = {
            "id": user.id, "tg_id": user.telegram_id, "role": user.role.value,
            "username": user.username, "first_name": user.first_name,
            "last_name": user.last_name, "hasSubscription": has_access,
        }
        
        response = make_response(jsonify({"token": token, "profile": profile_data}))
        response.set_cookie(
            'auth_token', value=token, max_age=60 * 60 * 24 * 7,
            path='/', httponly=True, samesite='Lax'
          )
        logger.info(f"Successfully authenticated user_id={user.id}. Token issued.")
        return response

    finally:
        db.close()

@bp.get("/api/auth/me")
def get_current_user():
    # ... (начало без изменений)
    jwt_secret = current_app.config.get("JWT_SECRET")
    token = request.cookies.get('auth_token')
    if not token: return jsonify({"error": "no_token"}), 401

    try:
        payload = jwt.decode(token, jwt_secret, algorithms=["HS256"])
        user_id = int(payload["sub"])
    except (jwt.ExpiredSignatureError, jwt.InvalidTokenError):
        logger.warning("Get /me failed: bad or expired token.")
        return jsonify({"error": "bad_token"}), 401

    logger.info(f"Get /me request for user_id={user_id}")
    db = next(get_db())
    try:
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            logger.error(f"Get /me failed: user_id={user_id} not found in DB.")
            return jsonify({"error": "user_not_found"}), 404

        db.refresh(user)

        # --- ГЛАВНОЕ ИСПРАВЛЕНИЕ ---
        # Проверяем подписку по ВНУТРЕННЕМУ ID (user.id)
        sub = get_active_subscription(db, user.id)
        is_admin = user.role == UserRole.admin
        has_access = is_admin or (sub is not None)
        
        logger.info(f"Get /me access check for user_id={user.id}: is_admin={is_admin}, subscription_found={sub is not None}, has_access={has_access}")

        return jsonify({
            "user": {
                "id": user.id, "tg_id": user.telegram_id, "role": user.role.value,
                "username": user.username, "first_name": user.first_name,
                "last_name": user.last_name, "hasSubscription": has_access,
            }
        })
    finally:
        db.close()
