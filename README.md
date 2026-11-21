# Proxy Shop Telegram Bot

Telegram-бот для продажи прокси с поддержкой пополнения баланса, реферальной системы и админ-панелью.

## Возможности

- 🛒 **Каталог прокси** — фильтрация по странам и типам (HTTP, HTTPS, SOCKS4, SOCKS5)
- 💰 **Баланс пользователя** — пополнение через CryptoBot или ЮMoney
- 📦 **Покупка прокси** — аренда на 1/7/30 дней с автопродлением
- 👥 **Реферальная программа** — бонус за привлеченных пользователей
- ⚙️ **Админ-панель** — управление прокси, пользователями, рассылки
- 📊 **Статистика** — отслеживание продаж и активности

## Быстрый старт

### 1. Клонирование и настройка

```bash
git clone <repo>
cd proxy-shop-bot
cp .env.example .env
```

### 2. Настройка `.env`

```env
BOT_TOKEN=your_bot_token_from_botfather
ADMIN_IDS=123456789,987654321
PAYMENT_PROVIDER=cryptobot
CRYPTOBOT_TOKEN=your_cryptobot_token
# или для ЮMoney:
# PAYMENT_PROVIDER=yoomoney
# YOOMONEY_TOKEN=your_token
# YOOMONEY_WALLET=41001xxxxxxxxxx
```

### 3. Запуск через Docker (рекомендуется)

```bash
docker-compose up -d --build
```

### 4. Запуск локально

```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
# venv\Scripts\activate  # Windows

pip install -r requirements.txt
python main.py
```

## Структура проекта

```
proxy-shop-bot/
├── main.py              # Точка входа
├── config.py            # Конфигурация
├── database.py          # Работа с SQLite (aiosqlite)
├── handlers.py          # Хендлеры бота
├── keyboards.py         # Клавиатуры
├── payments.py          # Платежные провайдеры
├── requirements.txt     # Зависимости
├── Dockerfile           # Docker образ
├── docker-compose.yml   # Docker Compose
├── .env.example         # Пример конфигурации
└── data/                # База данных (создается автоматически)
```

## Команды админа

| Команда | Описание |
|---------|----------|
| `/set_welcome <текст>` | Изменить приветствие |
| `/set_countries RU,US,DE` | Список стран |
| `/set_types http,socks5` | Типы прокси |
| `/broadcast <текст>` | Рассылка всем пользователям |

## Добавление прокси (админ)

1. Нажмите «⚙️ Админ панель» → «➕ Добавить прокси»
2. Пошагово введите: IP, порт, страну, город, тип, цены
3. Прокси появится в каталоге

Или через БД напрямую:
```sql
INSERT INTO proxies (ip, port, country, city, type, price_per_day, price_per_week, price_per_month)
VALUES ('1.2.3.4', 8080, 'RU', 'Moscow', 'http', 10, 60, 200);
```

## Платежные системы

### CryptoBot
1. Создайте приложение в @CryptoBot → «Crypto Pay API»
2. Получите токен и добавьте в `.env`
3. Бот будет создавать инвойсы в USDT

### ЮMoney
1. Получите токен: https://yoomoney.ru/myservices/new
2. Настройте Quickpay форму
3. Добавьте токен и номер кошелька в `.env`

## Вебхук (production)

Для продакшена рекомендуется использовать вебхук:

```env
WEBHOOK_URL=https://your-domain.com
WEBHOOK_PORT=8443
```

Настройте reverse proxy (nginx) с SSL на порт 8443.

### Nginx конфиг пример

```nginx
server {
    listen 443 ssl;
    server_name your-domain.com;
    
    ssl_certificate /path/to/cert.pem;
    ssl_certificate_key /path/to/key.pem;
    
    location /webhook {
        proxy_pass http://localhost:8443;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

## База данных

Используется SQLite (`data/bot.db`). Основные таблицы:
- `users` — пользователи, баланс, рефералы
- `proxies` — список прокси
- `purchases` — активные аренды
- `transactions` — история платежей
- `settings` — настройки бота

## Автопродление

- Включается пользователем для каждого прокси
- Списывается за 1 день до окончания
- Требует достаточного баланса

## Разработка

### Добавление нового платежного провайдера

1. Создайте класс, наследующий `PaymentProvider` в `payments.py`
2. Реализуйте методы `create_payment`, `check_payment`, `verify_webhook`
3. Добавьте в `get_payment_provider()`

### Запуск тестов

```bash
pytest tests/ -v
```

## Лицензия

MIT