# content.py 

from flask import Blueprint, request, jsonify, current_app
from database import get_db, User, Module 
from functools import wraps
import jwt

bp = Blueprint("auth_tg", __name__)

# --- Декоратор для проверки JWT-токена ---
def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.cookies.get('auth_token')
        if not token:
            return jsonify({"error": "token_missing"}), 401
        try:
            jwt_secret = current_app.config.get("JWT_SECRET")
            payload = jwt.decode(token, jwt_secret, algorithms=["HS256"])
            # Передаем user_id в обработчик
            kwargs['current_user_id'] = payload['sub']
        except (jwt.ExpiredSignatureError, jwt.InvalidTokenError):
            return jsonify({"error": "bad_token"}), 401
        return f(*args, **kwargs)
    return decorated

# --- Новый эндпоинт для получения модулей ---
@bp.get("/api/modules")
@token_required
def get_all_modules(current_user_id): # Получаем user_id из декоратора
    db = next(get_db())
    try:
        # Сортируем по полю position, чтобы модули шли в правильном порядке
        modules = db.query(Module).order_by(Module.position.asc()).all()
        
        # Преобразуем объекты SQLAlchemy в словари для JSON-ответа
        result = [
            {
                "id": m.id,
                "slug": m.slug,
                "title": m.title,
                "description": m.description,
                "position": m.position,
                "is_free": m.is_free
            } for m in modules
        ]
        return jsonify(result)
    finally:
        db.close()

