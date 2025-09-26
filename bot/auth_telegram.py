# auth_telegram.py
import hmac, hashlib, json, time, logging # Добавляем logging
from typing import Optional, Dict, Any
import jwt
from urllib.parse import parse_qsl
from flask import Blueprint, request, jsonify, current_app, make_response
from database import get_db, get_user_by_telegram_id, create_user, get_active_subscription, UserRole, User

# Настраиваем логгер
logger = logging.getLogger(__name__)
bp = Blueprint("auth_tg", __name__)

def check_telegram_auth(init_data: str, bot_token: str) -> Optional[Dict[str, Any]]:
    # ... (эта функция без изменений)
    if not init_data or not bot_token: return None
    data = dict(parse_qsl(init_data, keep_blank_values=True))
    recv_hash = data.pop("hash", None)
    if not recv_hash: return None
    check_str = "\n".join(f"{k}={data[k]}" for k in sorted(data.keys()))
    secret = hashlib.sha256(bot_token.encode("utf-8")).digest()
    calc_hash = hmac.new(secret, check_str.encode("utf-8"), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(calc_hash, recv_hash): return None
    return data

@bp.post("/api/auth/telegram")
def auth_telegram():
    body = request.get_json(silent=True) or {}
    
    # --- ОТЛАДОЧНЫЙ ЛОГ 1: Посмотреть, что приходит на бэкенд ---
    logger.info(f"Received auth request body: {body}")
    
    init_data = body.get("init_data", "")
    if not init_data:
        logger.error("Auth failed: 'init_data' field is missing in request body.")
        return jsonify({"error": "no_init_data"}), 400

    # --- ОТЛАДОЧНЫЙ ЛОГ 2: Посмотреть саму строку initData ---
    logger.info(f"BACKEND initData: {init_data}")

    bot_token = current_app.config.get("BOT_TOKEN")
    jwt_secret = current_app.config.get("JWT_SECRET")
    if not bot_token or not jwt_secret:
        logger.error("Auth failed: server is misconfigured (BOT_TOKEN or JWT_SECRET is missing).")
        return jsonify({"error": "server_misconfigured"}), 500

    # --- ОТЛАДОЧНЫЙ ЛОГ 3: Убедиться, что используется правильный токен ---
    token_preview = f"{bot_token[:4]}...{bot_token[-4:]}" if bot_token and len(bot_token) > 8 else "TOKEN_IS_INVALID_OR_SHORT"
    logger.info(f"Using token preview: {token_preview}")

    data = check_telegram_auth(init_data, bot_token)
    if not data:
        logger.warning("Auth failed: bad signature. Check if FRONTEND and BACKEND initData strings match exactly.")
        return jsonify({"error": "bad_signature"}), 401

    # --- Если мы дошли сюда, значит подпись верна! ---
    logger.info("Signature is OK. Proceeding with user check.")

    try:
        u = json.loads(data.get("user", "{}")) or {}
        tg_id = int(u.get("id"))
        logger.info(f"Auth attempt for tg_id={tg_id}")
    except Exception:
        logger.error("Auth failed: malformed user data in initData.")
        return jsonify({"error": "malformed_user"}), 400

    db = next(get_db())
    try:
        user = get_user_by_telegram_id(db, tg_id)
        if not user:
            logger.info(f"User with tg_id={tg_id} not found, creating new one.")
            user = create_user(db, tg_id, username=u.get("username"), first_name=u.get("first_name"), last_name=u.get("last_name"))
        
        logger.info(f"User found/created: internal_id={user.id}, tg_id={user.telegram_id}, role={user.role}")

        sub = get_active_subscription(db, user.id) 
        is_admin = user.role == UserRole.admin
        has_access = is_admin or (sub is not None)
        
        logger.info(f"Access check for user_id={user.id}: is_admin={is_admin}, subscription_found={sub is not None}, has_access={has_access}")

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
