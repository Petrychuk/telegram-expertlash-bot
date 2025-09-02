import os
from dotenv import load_dotenv
import pytest

# грузим .env перед тестами
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '..', '.env'))

@pytest.fixture(scope="session")
def anyio_backend():
    # если есть async-тесты – пусть pytest-anyio использует asyncio
    return "asyncio"
