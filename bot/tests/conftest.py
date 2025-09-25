# tests/conftest.py

import pytest
import os
import sys

# Добавляем корневую директорию в путь для импорта
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT_DIR)

from database import Base, get_db, engine
from webhook import app as flask_app

@pytest.fixture(scope="session")
def app():
    """Создает и настраивает экземпляр Flask-приложения для тестов."""
    flask_app.config.update({
        "TESTING": True,
        "JWT_SECRET": "test-secret", # Используем тестовый секрет
        "BOT_TOKEN": "123:test"
    })
    yield flask_app

@pytest.fixture(scope="session")
def client(app):
    """Предоставляет тестовый клиент для Flask-приложения."""
    return app.test_client()

@pytest.fixture(scope="function")
def db_session():
    """
    Создает чистую базу данных для каждого теста.
    Откатывает все изменения после теста.
    """
    # Создаем все таблицы
    Base.metadata.create_all(bind=engine)
    
    connection = engine.connect()
    transaction = connection.begin()
    
    # Создаем сессию, привязанную к этой транзакции
    db = next(get_db())
    db.begin_nested()

    # Передаем сессию в тест
    yield db

    # После завершения теста откатываем все изменения
    transaction.rollback()
    connection.close()
    
    # Удаляем все таблицы для полной изоляции
    Base.metadata.drop_all(bind=engine)

