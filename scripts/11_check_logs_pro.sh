#!/bin/bash
# -*- coding: utf-8 -*-

# ============================================
# ПРОВЕРКА ПОСЛЕДНИХ ЗАПИСЕЙ В ЛОГАХ
# ============================================

PROJECT_DIR="/root/Post-Bridge"
LOG_DIR="$PROJECT_DIR/logs"

# Цвета
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
MAGENTA='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m'

print_header() {
    echo -e "${BLUE}============================================${NC}"
    echo -e "${BLUE}  📊 ПРОВЕРКА ЛОГОВ И ДИАГНОСТИКА${NC}"
    echo -e "${BLUE}============================================${NC}"
}

print_section() {
    echo -e "\n${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${YELLOW}  $1${NC}"
    echo -e "${YELLOW}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
}

print_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
print_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
print_error() { echo -e "${RED}[ERROR]${NC} $1"; }
print_debug() { echo -e "${CYAN}[DEBUG]${NC} $1"; }

# ============================================
# ПРОВЕРКА ФАЙЛОВ
# ============================================

check_file() {
    local file=$1
    local lines=${2:-10}
    
    if [ -f "$file" ]; then
        echo -e "${GREEN}✅ Файл существует:${NC} $file"
        echo -e "${BLUE}Последние $lines строк:${NC}"
        tail -n "$lines" "$file" | sed 's/^/  /'
        echo ""
        return 0
    else
        echo -e "${RED}❌ Файл не найден:${NC} $file"
        return 1
    fi
}

check_file_with_grep() {
    local file=$1
    local pattern=$2
    local lines=${3:-5}
    
    if [ -f "$file" ]; then
        echo -e "${GREEN}✅ Файл:${NC} $file"
        echo -e "${BLUE}Последние $lines строк с '$pattern':${NC}"
        grep -i "$pattern" "$file" | tail -n "$lines" | sed 's/^/  /'
        if [ $? -ne 0 ]; then
            echo "  (нет записей)"
        fi
        echo ""
        return 0
    else
        echo -e "${RED}❌ Файл не найден:${NC} $file"
        return 1
    fi
}

# ============================================
# НОВАЯ ФУНКЦИЯ: ИСТОРИЯ ПРОВЕРОК ПОЧТЫ
# ============================================

check_email_history() {
    local log_file=$1
    local count=${2:-3}
    
    echo -e "${BLUE}Последние $count проверок почты:${NC}"
    
    if [ ! -f "$log_file" ]; then
        echo "  (лог не найден)"
        return
    fi
    
    # Ищем строки с проверкой почты и обработанными письмами
    local checks=$(grep -E "(Проверка почты|Найдено новых писем|Новых писем нет|Обработка письма)" "$log_file" | tail -20)
    
    if [ -z "$checks" ]; then
        echo "  (нет записей о проверке почты)"
        return
    fi
    
    # Парсим и выводим с группировкой по времени
    local current_time=""
    local check_num=0
    
    echo "$checks" | while IFS= read -r line; do
        # Извлекаем время из лога [2025-01-07 12:34:56]
        if [[ $line =~ \[([0-9]{4}-[0-9]{2}-[0-9]{2}\ [0-9]{2}:[0-9]{2}:[0-9]{2})\] ]]; then
            current_time="${BASH_REMATCH[1]}"
        fi
        
        # Определяем тип события
        if [[ $line == *"Проверка почты"* ]]; then
            echo -e "  ${CYAN}🔍 $current_time - НАЧАЛО ПРОВЕРКИ${NC}"
        elif [[ $line == *"Новых писем нет"* ]]; then
            echo -e "  ${YELLOW}📭 $current_time - ПИСЕМ НЕТ${NC}"
        elif [[ $line == *"Найдено новых писем"* ]]; then
            # Извлекаем количество
            if [[ $line =~ ([0-9]+) ]]; then
                echo -e "  ${GREEN}📨 $current_time - НАЙДЕНО ${BASH_REMATCH[1]} ПИСЕМ${NC}"
            else
                echo -e "  ${GREEN}📨 $current_time - НАЙДЕНЫ НОВЫЕ ПИСЬМА${NC}"
            fi
        elif [[ $line == *"Обработка письма от"* ]]; then
            # Извлекаем отправителя
            if [[ $line =~ Обработка\ письма\ от\ ([^[:space:]]+) ]]; then
                echo -e "  ${MAGENTA}✉️  $current_time - ПИСЬМО ОТ ${BASH_REMATCH[1]}${NC}"
            fi
        elif [[ $line == *"✅ Получен ответ"* ]]; then
            echo -e "  ${GREEN}✅ $current_time - ОТВЕТ ПОЛУЧЕН${NC}"
        elif [[ $line == *"FILTERED"* ]]; then
            echo -e "  ${RED}⏭️  $current_time - ПИСЬМО ОТФИЛЬТРОВАНО${NC}"
        elif [[ $line == *"❌"* ]] || [[ $line == *"ERROR"* ]]; then
            echo -e "  ${RED}❌ $current_time - ОШИБКА${NC}"
        fi
    done | tail -$((count * 5))  # Показываем достаточно строк для N проверок
}

# ============================================
# НОВАЯ ФУНКЦИЯ: СТАТИСТИКА ПОТЕРЬ
# ============================================

check_loss_statistics() {
    local log_file=$1
    
    echo -e "${BLUE}Статистика потерь писем:${NC}"
    
    if [ ! -f "$log_file" ]; then
        echo "  (лог не найден)"
        return
    fi
    
    # Считаем события за последние 24 часа
    local since=$(date -d '24 hours ago' '+%Y-%m-%d %H:%M:%S')
    
    local total_checks=$(grep -c "Проверка почты" "$log_file" 2>/dev/null || echo "0")
    local total_found=$(grep -c "Найдено новых писем" "$log_file" 2>/dev/null || echo "0")
    local total_empty=$(grep -c "Новых писем нет" "$log_file" 2>/dev/null || echo "0")
    local total_filtered=$(grep -c "FILTERED" "$log_file" 2>/dev/null || echo "0")
    local total_processed=$(grep -c "✅ Получен ответ" "$log_file" 2>/dev/null || echo "0")
    local total_errors=$(grep -c "ERROR" "$log_file" 2>/dev/null || echo "0")
    
    echo -e "  ${CYAN}📊 Всего проверок:${NC} $total_checks"
    echo -e "  ${GREEN}📨 Найдено писем:${NC} $total_found"
    echo -e "  ${YELLOW}📭 Пустых проверок:${NC} $total_empty"
    echo -e "  ${RED}⏭️  Отфильтровано:${NC} $total_filtered"
    echo -e "  ${GREEN}✅ Обработано:${NC} $total_processed"
    echo -e "  ${RED}❌ Ошибок:${NC} $total_errors"
    
    # Процент потерь
    if [[ -n "$total_found" && "$total_found" -gt 0 ]]; then
        local loss_rate=$(( (total_found - total_processed) * 100 / total_found ))
        if [[ "$loss_rate" -gt 50 ]]; then
            echo -e "  ${RED}⚠️  ВЫСОКИЙ УРОВЕНЬ ПОТЕРЬ: ${loss_rate}%${NC}"
        elif [[ "$loss_rate" -gt 20 ]]; then
            echo -e "  ${YELLOW}⚠️  СРЕДНИЙ УРОВЕНЬ ПОТЕРЬ: ${loss_rate}%${NC}"
        else
            echo -e "  ${GREEN}✅ НИЗКИЙ УРОВЕНЬ ПОТЕРЬ: ${loss_rate}%${NC}"
        fi
    fi
}

# ============================================
# НОВАЯ ФУНКЦИЯ: ПРОВЕРКА ПАПОК (IMAP)
# ============================================

check_imap_folders() {
    echo -e "${BLUE}Статус папок почтового ящика:${NC}"
    
    # Проверяем через python с таймаутом
    cd "$PROJECT_DIR" 2>/dev/null
    python3 <<'EOF' 2>/dev/null
import sys
import yaml
import imaplib
import socket
import signal

# Таймаут на всё
signal.signal(signal.SIGALRM, lambda x, y: sys.exit(1))
signal.alarm(10)

try:
    with open('config/secrets.yaml', 'r') as f:
        secrets = yaml.safe_load(f)
    
    email_config = secrets.get('email', {})
    socket.setdefaulttimeout(10)
    
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
        except Exception:
            pass
    
    imap.close()
    imap.logout()
    
except Exception:
    pass
EOF
    cd - > /dev/null 2>&1 || true
}

# ============================================
# ОСНОВНАЯ ФУНКЦИЯ
# ============================================

check_logs() {
    local lines=${1:-10}
    
    print_header
    
    # Текущая дата
    DATE=$(date +%Y%m%d)
    LOG_FILE="$LOG_DIR/deepseek_bridge_$DATE.log"
    
    # ===== 1. ИСТОРИЯ ПРОВЕРОК ПОЧТЫ (НОВОЕ!) =====
    print_section "1. 📋 ИСТОРИЯ ПРОВЕРОК ПОЧТЫ (последние 3)"
    check_email_history "$LOG_FILE" 3
    echo ""
    
    # ===== 2. СТАТИСТИКА ПОТЕРЬ (НОВОЕ!) =====
    print_section "2. 📊 СТАТИСТИКА ПОТЕРЬ ПИСЕМ"
    check_loss_statistics "$LOG_FILE"
    echo ""
    
    # ===== 3. СТАТУС ПАПОК (НОВОЕ!) =====
    print_section "3. 📁 СТАТУС ПАПОК ПОЧТОВОГО ЯЩИКА"
    check_imap_folders
    echo ""
    
    # ===== 4. ПОСЛЕДНИЕ СОБЫТИЯ В ЛОГЕ =====
    print_section "4. 📝 ПОСЛЕДНИЕ СОБЫТИЯ В ЛОГЕ"
    if [ -f "$LOG_FILE" ]; then
        echo -e "${BLUE}Последние $lines строк:${NC}"
        tail -n "$lines" "$LOG_FILE" | sed 's/^/  /'
    else
        echo "  (лог не найден)"
    fi
    echo ""
    
    # ===== 5. ПОСЛЕДНИЕ ОШИБКИ =====
    print_section "5. ❌ ПОСЛЕДНИЕ ОШИБКИ"
    if [ -f "$LOG_FILE" ]; then
        echo -e "${BLUE}Ошибки в логе:${NC}"
        grep -i "error\|fail\|exception\|❌" "$LOG_FILE" 2>/dev/null | tail -5 | sed 's/^/  /' || echo "  (нет ошибок)"
    else
        echo "  (лог не найден)"
    fi
    echo ""
    
    # ===== 6. СТАТУС ПРОЦЕССОВ =====
    print_section "6. 🖥️ СТАТУС ПРОЦЕССОВ"
    
    # Проверка моста
    if pgrep -f "email_bridge.py" > /dev/null; then
        PID=$(pgrep -f "email_bridge.py" | head -1)
        print_info "✅ Мост запущен (PID: $PID)"
        echo "   CPU: $(ps -p $PID -o %cpu= 2>/dev/null | xargs)%"
        echo "   RAM: $(ps -p $PID -o %mem= 2>/dev/null | xargs)%"
        echo "   Время работы: $(ps -p $PID -o etime= 2>/dev/null | xargs)"
    else
        print_error "❌ Мост НЕ ЗАПУЩЕН"
    fi
    
    echo ""
    
    # Проверка сервера
    if pgrep -f "app.py" > /dev/null; then
        PID=$(pgrep -f "app.py" | head -1)
        print_info "✅ Сервер запущен (PID: $PID)"
        echo "   CPU: $(ps -p $PID -o %cpu= 2>/dev/null | xargs)%"
        echo "   RAM: $(ps -p $PID -o %mem= 2>/dev/null | xargs)%"
        echo "   Время работы: $(ps -p $PID -o etime= 2>/dev/null | xargs)"
    else
        print_error "❌ Сервер НЕ ЗАПУЩЕН"
    fi
    
    echo ""
    
    # ===== 7. ДИАГНОСТИЧЕСКИЙ ФАЙЛ =====
    print_section "7. 📄 ДИАГНОСТИЧЕСКИЙ ФАЙЛ"
    if [ -f "$LOG_DIR/email_diagnostics.json" ]; then
        echo -e "${BLUE}Содержимое диагностики:${NC}"
        cat "$LOG_DIR/email_diagnostics.json" 2>/dev/null | python3 -m json.tool 2>/dev/null | sed 's/^/  /' || echo "  (ошибка парсинга)"
    else
        echo "  (диагностика не найдена)"
    fi
    
    echo ""
    
    # ===== 8. СОВЕТЫ =====
    print_section "8. 💡 СОВЕТЫ ПО ВОССТАНОВЛЕНИЮ"
    
    # Проверяем наличие писем в Filtered
    if [ -f "$LOG_DIR/email_diagnostics.json" ]; then
        FILTERED_COUNT=$(grep -o '"filtered":[0-9]*' "$LOG_DIR/email_diagnostics.json" 2>/dev/null | cut -d: -f2 | tail -1)
        if [ -n "$FILTERED_COUNT" ] && [ "$FILTERED_COUNT" -gt 0 ] 2>/dev/null; then
            echo -e "  ${YELLOW}⚠️ Обнаружено $FILTERED_COUNT отфильтрованных писем${NC}"
            echo "   Для восстановления выполните:"
            echo "     python src/email_bridge.py --recover"
            echo "     или"
            echo "     python src/recover_filtered.py"
        else
            echo "  ✅ Отфильтрованных писем не обнаружено"
        fi
    else
        echo "  ℹ️ Для получения диагностики запустите мост"
    fi
    
    echo -e "${BLUE}============================================${NC}"
}

# ============================================
# ПАРСИНГ АРГУМЕНТОВ
# ============================================

LINES=10

case "$1" in
    -n|--lines)
        LINES="$2"
        shift 2
        ;;
    -f|--follow)
        echo -e "${BLUE}📡 Режим наблюдения (обновление каждые 10 сек, Ctrl+C для выхода)${NC}"
        while true; do
            clear
            check_logs "$LINES"
            echo -e "${YELLOW}Обновление каждые 10 секунд...${NC}"
            sleep 10
        done
        ;;
    -e|--errors)
        print_header
        print_section "❌ ОШИБКИ В ЛОГАХ"
        DATE=$(date +%Y%m%d)
        LOG_FILE="$LOG_DIR/deepseek_bridge_$DATE.log"
        echo -e "${BLUE}Лог моста:${NC}"
        grep -i "error\|fail\|exception\|❌" "$LOG_FILE" 2>/dev/null | tail -20 | sed 's/^/  /' || echo "  (нет ошибок)"
        echo ""
        echo -e "${BLUE}Лог сервера:${NC}"
        grep -i "error\|fail\|exception" "$LOG_DIR/deepseek_server.log" 2>/dev/null | tail -20 | sed 's/^/  /' || echo "  (нет ошибок)"
        echo ""
        echo -e "${BLUE}Ошибки сервиса:${NC}"
        grep -i "error\|fail\|exception" "$LOG_DIR/service_error.log" 2>/dev/null | tail -20 | sed 's/^/  /' || echo "  (нет ошибок)"
        ;;
    -h|--help)
        echo ""
        echo "Использование: $0 [опции]"
        echo ""
        echo "Опции:"
        echo "  -n, --lines N    - показать N строк (по умолчанию 10)"
        echo "  -f, --follow     - режим наблюдения (обновление каждые 10 сек)"
        echo "  -e, --errors     - показать только ошибки"
        echo "  -h, --help       - показать эту справку"
        echo ""
        echo "Примеры:"
        echo "  $0               - полная диагностика"
        echo "  $0 -n 20         - показать 20 строк лога"
        echo "  $0 -f            - следить за логами в реальном времени"
        echo "  $0 -e            - показать только ошибки"
        echo ""
        ;;
    *)
        check_logs "$LINES"
        ;;
esac