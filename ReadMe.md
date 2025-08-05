# Проект: telegram-expertlash-bot + React Web App

## Общая структура монорепозитория
```
telegram-expertlash-bot/         # Корневая папка проекта
├── bot                               # Корневая папка для логики бота
│   ├── venv
│   ├── .env                          # Обновленный файл переменных окружения для бота
│   ├── main.py                       # Теперь это bot_updated.py
│   ├── requirements.txt              # Обновленный файл зависимостей для бота
│   ├── .gitignore
│   ├── config.py                     # Новая конфигурация бота
│   ├── payment_config.py             # Настройки платежных систем
│   ├── database.py                   # Модели БД и функции
│   ├── payment_service.py            # Сервисы PayPal/Stripe
│   ├── telegram_service.py           # Сервис Telegram уведомлений
│   ├── test_system.py                # Скрипт тестирования для бота
│   └── subscriptions.db              # База данных SQLite (создается автоматически)
├── webapp/                     # React Web App для интерфейса курсов
│   ├── public/                 # Статические файлы (index.html, favicon…)
│   ├── src/
│   │   ├── components/         # UI-компоненты
│   │   ├── pages/              # Страницы (Catalog, Course, Profile…)
│   │   ├── App.js              # Корневой React-компонент
│   │   └── index.js            # Точка входа
│   ├── package.json            # Зависимости и скрипты React
│   └── .env.example            # Пример переменных окружения
├── webhook_server.py                 # Flask сервер для вебхуков (или в отдельной папке)
└── README.md                   # Описание проекта и инструкция по запуску
```

## Детали по папкам

### 1. Папка `bot/` (Python)
- **main.py** — бот на aiogram с командами, меню и интеграцией с каналом/группой.
- **requirements.txt** — список: `aiogram`, `python-dotenv`, `pydantic` и т.п.
- **.env.example** — пример:
  ```dotenv
  BOT_TOKEN=ваш_токен
  ADMIN_IDS=123,456
  CHANNEL_ID=@your_channel
  DATABASE_URL=sqlite:///db.sqlite3
  ```
- **venv/** — виртуальное окружение (не пушить в Git, добавить в `.gitignore`).

**Запуск Python-бота**:
```bash
cd bot
python3 -m venv venv
source venv/bin/activate    # или venv\Scripts\Activate.ps1
pip install -r requirements.txt
cp .env.example .env        # и заполнить реальные значения
python main.py
```

### 2. Папка `webapp/` (React)
- **public/index.html** — точка монтирования React.
- **src/App.js** — маршруты (React Router) для страниц:
  - `/catalog` — список курсов с карточками.
  - `/course/:id` — страница курса, уроки и описание.
  - `/profile` — настройки пользователя и подписки.
- **src/components/** — переиспользуемые UI-элементы (Card, Button, Header).
- **package.json** и **package-lock.json** — зависимости (react, react-dom, react-router-dom, axios, tailwindcss и т. д.).

**Запуск Web App**:
```bash
cd webapp
npm install
cp .env.example .env       # например, REACT_APP_API_URL=https://api.example.com
npm start
```

## Как это работает вместе
1. **Backend** (`bot/`) отвечает на команды в Telegram, хранит данные в БД и предоставляет API (если нужно) для фронтенда.
2. **Frontend** (`webapp/`) — независимое SPA, которое можно открыть в браузере или через Telegram Web App.
3. **Интеграция в Telegram**:
   - Кнопка `Open Catalog` из бота задаёт `WebAppInfo(url)`, открывает ваш React-приложение внутри клиента.
   - React-приложение берёт контент (курсы, уроки) через REST API вашего бэкенда или напрямую генерирует ссылки на Telegram-сообщения.
   

## Дальнейшие шаги
- Создать API в `bot/` (Flask/FastAPI) для реактивного фронтенда, либо отдавать JSON через тайминговые сообщения.
- Настроить CORS и переменные окружения для Netlify (webapp) и Render/Heroku (bot).
- Развернуть `webapp/` на Netlify/Vercel и `bot/` на Render/Heroku.
