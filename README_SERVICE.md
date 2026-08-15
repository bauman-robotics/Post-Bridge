# 📋 Systemd Service для Post Bridge

## 📁 Файл сервиса

Создайте файл `/etc/systemd/system/post-bridge.service`:

```bash
sudo nano /etc/systemd/system/post-bridge.service


[Unit]
Description=Post Bridge - DeepSeek Email Bridge
After=network.target
Wants=network-online.target

[Service]
Type=oneshot
RemainAfterExit=yes
User=root
WorkingDirectory=/root/Post-Bridge
ExecStart=/root/Post-Bridge/scripts/01_run___server_and_client____run_all.sh start
ExecStop=/root/Post-Bridge/scripts/01_run___server_and_client____run_all.sh stop
ExecReload=/root/Post-Bridge/scripts/01_run___server_and_client____run_all.sh restart
StandardOutput=append:/root/Post-Bridge/logs/service.log
StandardError=append:/root/Post-Bridge/logs/service_error.log
TimeoutStartSec=60
TimeoutStopSec=60

[Install]
WantedBy=multi-user.target


🚀 Запуск и управление
1. Перечитать конфигурацию systemd
bash

systemctl daemon-reload

2. Включить автозапуск при старте системы
bash

systemctl enable post-bridge

3. Запустить сервис
bash

systemctl start post-bridge

4. Проверить статус
bash

systemctl status post-bridge

5. Остановить сервис
bash

systemctl stop post-bridge

6. Перезапустить сервис
bash

systemctl restart post-bridge

7. Отключить автозапуск
bash

systemctl disable post-bridge

📊 Диагностика
Проверка логов
bash

# Лог сервиса (запуск/остановка)
tail -f /root/Post-Bridge/logs/service.log

# Лог ошибок сервиса
tail -f /root/Post-Bridge/logs/service_error.log

# Лог сервера DeepSeek
tail -f /root/Post-Bridge/logs/deepseek_server.log

# Лог моста
tail -f /root/Post-Bridge/logs/bridge.log

# Логи systemd
journalctl -u post-bridge -f

# Последние 50 строк логов systemd
journalctl -u post-bridge -n 50

Проверка процессов
bash

# Проверить, запущен ли сервер
ps aux | grep "app.py"

# Проверить, запущен ли мост
ps aux | grep "email_bridge"

# Проверить порты
ss -tulpn | grep -E "8000|8001"

Проверка работы сервера
bash

# Health-check
curl http://localhost:8001/healthz

# Должен ответить: {"status":"ok"}

🐛 Устранение проблем
Проблема: Сервис не запускается
bash

# Проверить статус
systemctl status post-bridge

# Посмотреть логи
journalctl -u post-bridge -n 50 --no-pager

# Проверить, есть ли ошибки в скрипте
/root/Post-Bridge/scripts/01_run___server_and_client____run_all.sh start

Проблема: Порт занят
bash

# Найти процесс на порту
lsof -i :8001

# Убить процесс
kill -9 $(lsof -i :8001 -t)

# Или
fuser -k 8001/tcp

Проблема: Процессы не запускаются после перезагрузки
bash

# Проверить, включен ли автозапуск
systemctl is-enabled post-bridge

# Если disabled, включить
systemctl enable post-bridge

# Проверить статус после перезагрузки
systemctl status post-bridge

Проблема: Сессия DeepSeek истекла
bash

# Обновить сессию
cd /root/Post-Bridge/Deepseek-API
source ../venv/bin/activate
python -m deepseek.auth

📋 Полный цикл перезапуска

Если нужно полностью перезапустить всё:
bash

# 1. Остановить сервис
systemctl stop post-bridge

# 2. Убить все процессы (если остались)
pkill -f "app.py"
pkill -f "email_bridge.py"

# 3. Очистить логи (опционально)
> /root/Post-Bridge/logs/deepseek_server.log
> /root/Post-Bridge/logs/bridge.log

# 4. Запустить сервис
systemctl start post-bridge

# 5. Проверить
systemctl status post-bridge
ps aux | grep -E "app.py|email_bridge"

🔧 Настройка порта

Если нужно изменить порт сервера:

    Создайте .env в папке Deepseek-API:
    bash

    echo "PORT=8001" > /root/Post-Bridge/Deepseek-API/.env

    Обновите config/config.yaml:
    yaml

    deepseek:
      api_url: "http://localhost:8001"

    Перезапустите сервис:
    bash

    systemctl restart post-bridge

✅ Проверка работоспособности
bash

# 1. Статус сервиса
systemctl status post-bridge

# 2. Процессы
ps aux | grep -E "app.py|email_bridge"

# 3. Health-check
curl http://localhost:8001/healthz

# 4. Проверить, что мост видит почту
tail -20 /root/Post-Bridge/logs/bridge.log | grep -E "Проверка|Найдено|Новых"

🗑️ Удаление сервиса
bash

# 1. Остановить и отключить
systemctl stop post-bridge
systemctl disable post-bridge

# 2. Удалить файл
rm /etc/systemd/system/post-bridge.service

# 3. Перечитать конфигурацию
systemctl daemon-reload