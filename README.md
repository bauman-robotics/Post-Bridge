# 📧 DeepSeek Email Bridge

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.9+-blue.svg" alt="Python">
  <img src="https://img.shields.io/badge/DeepSeek-API-green.svg" alt="DeepSeek">
  <img src="https://img.shields.io/badge/License-MIT-yellow.svg" alt="License">
</p>

## 📖 О проекте

**DeepSeek Email Bridge** — это система, которая автоматически обрабатывает запросы, поступающие по электронной почте, и отправляет ответы через DeepSeek API.

### Как это работает

1. Пользователь отправляет письмо на указанный email-адрес
2. Скрипт проверяет почту, извлекает вопрос
3. Запрос отправляется в DeepSeek API
4. Ответ отправляется обратно пользователю по email
5. Все ответы сохраняются в папке `email_responses/`

---

## 🚀 Возможности

- ✅ **Автоматическая обработка писем** — проверка почты по расписанию
- ✅ **Интеграция с DeepSeek** — использование бесплатного API
- ✅ **Фильтрация писем** — по теме, отправителю, содержимому
- ✅ **Сохранение ответов** — в JSON и Markdown форматах
- ✅ **Логирование** — подробные логи всех действий
- ✅ **Управление процессами** — скрипты для запуска/остановки
- ✅ **Безопасность** — секреты в отдельном файле (не в git)

---

## 📁 Структура проекта
```
12_Post_Bridge/
├── config/
│   ├── config.yaml
│   └── secrets.yaml
├── src/
│   ├── __init__.py
│   ├── email_bridge.py
│   ├── deepseek_client.py
│   ├── email_reader.py
│   ├── email_sender.py
│   ├── batch_processor.py
│   └── logger.py
├── scripts/
│   ├── 01_run___server_and_client____run_all.sh
│   ├── 02_stop_server.sh
│   ├── 03_stop_client__bridge.sh
│   ├── 04_run_server_only.sh
│   ├── 05_run_bridge___client_only.sh
│   └── 06_check_status__server_and_client.sh
├── Deepseek-API/
│   └── session/
├── email_responses/
│   └── json/
├── logs/
├── venv/
├── .gitignore
├── README.md
└── requirements.txt

🛠️ Установка
1. Клонирование репозитория
bash

git clone <repository-url>
cd 12_Post_Bridge

2. Создание виртуального окружения
bash

python3 -m venv venv
source venv/bin/activate  # Linux/Mac
# или
venv\Scripts\activate     # Windows

3. Установка зависимостей
bash

pip install -r requirements.txt
pip install pyyaml requests  # если requirements.txt нет

4. Настройка DeepSeek API
bash

# Клонируем DeepSeek API
git clone https://github.com/sums001/Deepseek-API.git

# Устанавливаем зависимости и проходим авторизацию
cd Deepseek-API
pip install -r requirements.txt
playwright install chromium
python -m deepseek.auth

5. Настройка конфигурации

Создайте файл config/secrets.yaml:
yaml

email:
  username: "your_email@yandex.ru"
  password: "your_app_password"
  imap_server: "imap.yandex.ru"
  smtp_server: "smtp.yandex.ru"
  smtp_port: 465

Важно: Для Яндекса используйте пароль приложения, а не основной пароль.

Настройте config/config.yaml под свои нужды (фильтры, интервалы и т.д.).
🚀 Запуск
Быстрый старт
bash

# Дать права на выполнение скриптам
chmod +x scripts/*.sh

# Запустить всё (сервер + мост)
./scripts/01_run___server_and_client____run_all.sh 

Управление компонентами
Команда	Описание
./scripts/01_run___server_and_client____run_all.sh start	Запуск всех сервисов
./scripts/01_run___server_and_client____run_all.sh stop	Остановка всех сервисов
./scripts/01_run___server_and_client____run_all.sh status	Проверка статуса
./scripts/01_run___server_and_client____run_all.sh restart	Перезапуск
./scripts/01_run___server_and_client____run_all.sh once	Одноразовая проверка почты
Отдельные компоненты
bash

# Только сервер
./scripts/04_run_server_only.sh
./scripts/04_run_server_only.sh start
./scripts/04_run_server_only.sh stop
./scripts/04_run_server_only.sh status

# Только мост
./scripts/05_run_bridge___client_only.sh
./scripts/05_run_bridge___client_only.sh start
./scripts/05_run_bridge___client_only.sh once   # Одноразово
./scripts/05_run_bridge___client_only.sh stop
./scripts/05_run_bridge___client_only.sh status

# Проверка статуса всех компонентов
./scripts/05_check_status.sh
./scripts/05_check_status.sh --watch  # Обновление каждые 5 сек
./scripts/05_check_status.sh --short  # Краткий вывод

# Убить процесс на порту
./scripts/02_stop_server.sh           # Порт 8001
./scripts/02_stop_server.sh 8080      # Другой порт
./scripts/02_stop_server.sh --force   # Принудительно

# Проверить статус сервера и клиента
06_check_status__server_and_client.sh

⚙️ Конфигурация
Основной конфиг (config/config.yaml)
yaml

general:
  mode: "server"                    # server | once
  email_check_interval: 120         # Секунд между проверками
  max_emails_per_check: 5           # Максимум писем за раз

deepseek:
  api_url: "http://localhost:8001"
  model: "deepseek-chat"
  temperature: 0.7
  max_tokens: 2000

filters:
  subject_contains: ["deepseek"]    # Обязательные слова в теме
  subject_not_contains: ["spam"]    # Запрещенные слова
  from_whitelist: []                # Разрешенные отправители
  from_blacklist: []                # Запрещенные отправители

Секреты (config/secrets.yaml)
yaml

email:
  username: "********@ya.ru"
  password: "your_app_password"
  imap_server: "imap.yandex.ru"
  smtp_server: "smtp.yandex.ru"
  smtp_port: 465

📊 Мониторинг
Просмотр логов
bash

# Лог сервера
tail -f logs/deepseek_server.log

# Лог моста
tail -f logs/bridge.log

# Оба лога
tail -f logs/*.log

# Через скрипты
./scripts/04_run_server_only.sh logs
./scripts/05_run_bridge___client_only.sh logs


    Секреты хранятся в config/secrets.yaml (не в git)

    Пароль приложения используется вместо основного пароля

    Сессия DeepSeek хранится в Deepseek-API/session/ (не в git)

    Логи не содержат паролей

📋 Требования

    Python 3.9+

    Playwright (для авторизации DeepSeek)

    Доступ к IMAP/SMTP (почта)

    Интернет (для работы с DeepSeek API)