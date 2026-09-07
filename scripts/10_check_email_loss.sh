#!/bin/bash
# -*- coding: utf-8 -*-

# ============================================
# ДИАГНОСТИКА ПОТЕРЯННЫХ ПИСЕМ
# ============================================

PROJECT_DIR="/root/Post-Bridge"
LOG_DIR="$PROJECT_DIR/logs"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

print_header() {
    echo -e "${BLUE}============================================${NC}"
    echo -e "${BLUE}  🔍 ДИАГНОСТИКА ПОТЕРЯННЫХ ПИСЕМ${NC}"
    echo -e "${BLUE}============================================${NC}"
}

echo ""
print_header

DATE=$(date +%Y%m%d)
LOG_FILE="$LOG_DIR/deepseek_bridge_$DATE.log"

if [ ! -f "$LOG_FILE" ]; then
    echo -e "${RED}❌ Лог не найден: $LOG_FILE${NC}"
    exit 1
fi

echo -e "\n${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${YELLOW}  1. ПОСЛЕДНИЕ 5 ПРОВЕРОК ПОЧТЫ${NC}"
echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

# Показываем последние 5 проверок с деталями
grep -E "(Проверка почты|Найдено новых писем|Новых писем нет|Обработка письма|✅ Получен ответ|FILTERED)" "$LOG_FILE" | tail -30 | while IFS= read -r line; do
    if [[ $line == *"Проверка почты"* ]]; then
        echo -e "\n${BLUE}🔍 $line${NC}"
    elif [[ $line == *"Новых писем нет"* ]]; then
        echo -e "  ${YELLOW}📭 $line${NC}"
    elif [[ $line == *"Найдено новых писем"* ]]; then
        echo -e "  ${GREEN}📨 $line${NC}"
    elif [[ $line == *"Обработка письма от"* ]]; then
        echo -e "  ${MAGENTA}✉️  $line${NC}"
    elif [[ $line == *"✅ Получен ответ"* ]]; then
        echo -e "  ${GREEN}✅ $line${NC}"
    elif [[ $line == *"FILTERED"* ]]; then
        echo -e "  ${RED}⏭️  $line${NC}"
    fi
done

echo -e "\n${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${YELLOW}  2. СТАТИСТИКА ЗА ПОСЛЕДНИЙ ЧАС${NC}"
echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

# Статистика за последний час
SINCE=$(date -d '1 hour ago' '+%Y-%m-%d %H:')
CHECKS=$(grep "$SINCE" "$LOG_FILE" | grep -c "Проверка почты")
FOUND=$(grep "$SINCE" "$LOG_FILE" | grep -c "Найдено новых писем")
EMPTY=$(grep "$SINCE" "$LOG_FILE" | grep -c "Новых писем нет")
FILTERED=$(grep "$SINCE" "$LOG_FILE" | grep -c "FILTERED")
PROCESSED=$(grep "$SINCE" "$LOG_FILE" | grep -c "✅ Получен ответ")
ERRORS=$(grep "$SINCE" "$LOG_FILE" | grep -c "ERROR")

echo -e "  ${BLUE}Проверок:${NC} $CHECKS"
echo -e "  ${GREEN}Найдено писем:${NC} $FOUND"
echo -e "  ${YELLOW}Пустых проверок:${NC} $EMPTY"
echo -e "  ${RED}Отфильтровано:${NC} $FILTERED"
echo -e "  ${GREEN}Обработано:${NC} $PROCESSED"
echo -e "  ${RED}Ошибок:${NC} $ERRORS"

if [ $FOUND -gt 0 ] && [ $PROCESSED -lt $FOUND ]; then
    LOST=$((FOUND - PROCESSED - FILTERED))
    echo -e "  ${RED}💀 ПОТЕРЯНО ПИСЕМ:${NC} $LOST"
fi

echo -e "\n${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${YELLOW}  3. ПРОВЕРКА ПАПОК (IMAP)${NC}"
echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"

# Проверка папок через Python
cd "$PROJECT_DIR" 2>/dev/null
python3 <<'EOF'
import sys
import yaml
import imaplib
from pathlib import Path

try:
    with open('config/secrets.yaml', 'r') as f:
        secrets = yaml.safe_load(f)
    
    email_config = secrets.get('email', {})
    
    imap = imaplib.IMAP4_SSL(email_config.get('imap_server', 'imap.yandex.ru'))
    imap.login(email_config['username'], email_config['password'])
    
    folders = ['INBOX', 'Filtered', 'Errors', 'Processed']
    
    for folder in folders:
        try:
            imap.select(folder)
            status, messages = imap.search(None, 'ALL')
            if status == 'OK':
                total = len(messages[0].split()) if messages[0] else 0
                status, unseen = imap.search(None, 'UNSEEN')
                unseen_count = len(unseen[0].split()) if unseen and unseen[0] else 0
                print(f"  📁 {folder}: {total} писем (непрочитанных: {unseen_count})")
                
                # Показываем последние 3 письма из Filtered
                if folder == 'Filtered' and total > 0:
                    print(f"     Последние письма в Filtered:")
                    for email_id in messages[0].split()[-3:]:
                        status, data = imap.fetch(email_id, '(BODY.PEEK[HEADER.FIELDS (SUBJECT FROM)])')
                        if status == 'OK':
                            header = data[0][1].decode()
                            subject = [l for l in header.split('\n') if l.startswith('Subject:')]
                            if subject:
                                print(f"       - {subject[0][:60]}")
            else:
                print(f"  ❌ {folder}: не доступна")
        except Exception as e:
            print(f"  ⚠️ {folder}: ошибка")
    
    imap.close()
    imap.logout()
    
except Exception as e:
    print(f"  ❌ Ошибка подключения: {str(e)[:50]}")
EOF
cd - > /dev/null 2>&1

echo -e "\n${BLUE}============================================${NC}"
echo -e "${GREEN}✅ Диагностика завершена${NC}"
echo -e "${BLUE}============================================${NC}\n"