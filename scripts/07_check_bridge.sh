#!/bin/bash
# Проверка здоровья моста

LOG_FILE="/root/Post-Bridge/logs/deepseek_bridge_$(date +%Y%m%d).log"

# Проверяем, есть ли процесс
if ! pgrep -f "email_bridge.py" > /dev/null; then
    echo "❌ Мост не запущен, перезапускаю..."
    systemctl restart post-bridge
    exit 0
fi

# Проверяем, было ли обновление лога за последние 5 минут
if [ -f "$LOG_FILE" ]; then
    LAST_LINE=$(tail -1 "$LOG_FILE")
    if echo "$LAST_LINE" | grep -q "Проверка почты"; then
        echo "✅ Мост работает"
    else
        echo "⚠️ Мост завис (нет записей о проверке), перезапускаю..."
        systemctl restart post-bridge
    fi
else
    echo "⚠️ Лог не найден, перезапускаю..."
    systemctl restart post-bridge
fi