# auth_telegram.py
from __future__ import annotations
import hmac, hashlib, json, time
from typing import Optional, Dict, Any
import jwt
from urllib.parse import parse_qsl
# ИМПОРТИРУЕМ НУЖНЫЕ ИНСТРУМЕНТЫ ИЗ FLASK
from flask import Blueprint, request, jsonify, current_app, make_response

# ИМПОРТИРУЕМ ВАШИ ФУНКЦИИ И МОДЕЛИ
from database import get_db, get_user_by_telegram_id, create_user, get_active_subscription, User, Subscription 

bp = Blueprint("auth_tg", __name__)

# Функция check_telegram_auth остается без изменений
def check_telegram_auth(init_data: str, bot_token: str) -> Optional[Dict[str, Any]]:
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
    # На фронте мы отправляем { init_data: ... }, поэтому ищем init_data
    init_data = body.get("init_data", "")
    if not init_data: return jsonify({"error": "no_init_data"}), 400

    bot_token = current_app.config.get("BOT_TOKEN")
    jwt_secret = current_app.config.get("JWT_SECRET")
    if not bot_token or not jwt_secret: return jsonify({"error": "server_misconfigured"}), 500

    data = check_telegram_auth(init_data, bot_token)
    if not data: return jsonify({"error": "bad_signature"}), 401

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

        is_admin = user.role == 'admin'
        sub = get_active_subscription(db, user.id) 
        has_access = is_admin or (sub is not None)

        if not has_access:
            return jsonify({"error": "no_subscription"}), 403

        now = int(time.time())
        payload = {"sub": user.id, "iat": now, "exp": now + 60 * 60 * 24 * 7, "role": user.role}
        token = jwt.encode(payload, jwt_secret, algorithm="HS256")

        profile_data = {
            "id": user.id, "tg_id": user.telegram_id, "role": user.role,
            "username": user.username, "first_name": user.first_name,
            "last_name": user.last_name, "hasSubscription": has_access,
        }
        
        # --- СОЗДАЕМ ОТВЕТ И УСТАНАВЛИВАЕМ COOKIE С ПОМОЩЬЮ FLASK ---
        # Вместо NextResponse.json используем jsonify
        response = make_response(jsonify({"token": token, "profile": profile_data}))
        
        # Вместо response.set_cookie(...) используем тот же метод на объекте ответа Flask
        response.set_cookie(
            'auth_token', 
            value=token, 
            max_age=60 * 60 * 24 * 7, # 7 дней
            path='/', 
            httponly=True, 
            samesite='Lax'
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
    except (jwt.ExpiredSignatureError, jwt.InvalidTokenError):
        return jsonify({"error": "bad_token"}), 401

    db = next(get_db())
    try:
        user = db.query(User).filter(User.id == user_id).first()
        if not user:
            return jsonify({"error": "user_not_found"}), 404

        # --- ДОБАВЛЕНО ИСПРАВЛЕНИЕ ---
        db.refresh(user) # Принудительно обновить объект user из БД
        # ---------------------------

        is_admin = user.role == 'admin'
        sub = get_active_subscription(db, user.id)
        has_access = is_admin or (sub is not None)

        return jsonify({
            "user": {
                "id": user.id,
                "tg_id": user.telegram_id,
                "role": user.role,
                "username": user.username,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "hasSubscription": has_access,
            }
        })
    finally:
        db.close()