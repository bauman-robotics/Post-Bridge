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
NC='\033[0m'

print_header() {
    echo -e "${BLUE}============================================${NC}"
    echo -e "${BLUE}  📊 ПРОВЕРКА ЛОГОВ${NC}"
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
# ОСНОВНАЯ ФУНКЦИЯ
# ============================================

check_logs() {
    local lines=${1:-10}
    
    print_header
    
    # Текущая дата
    DATE=$(date +%Y%m%d)
    
    # ===== 1. БРИДЖ ЛОГ =====
    print_section "1. ПОЧТОВЫЙ МОСТ (bridge.log)"
    check_file "$LOG_DIR/bridge.log" "$lines"
    
    # ===== 2. ДИПСИК БРИДЖ ЛОГ =====
    #print_section "2. DEEPSEEK БРИДЖ (deepseek_bridge.log)"
    #check_file "$LOG_DIR/deepseek_bridge.log" "$lines"
    
    # ===== 3. ДНЕВНОЙ ЛОГ БРИДЖА =====
    print_section "3. ДНЕВНОЙ ЛОГ БРИДЖА (deepseek_bridge_$DATE.log)"
    check_file "$LOG_DIR/deepseek_bridge_$DATE.log" "$lines"
    
    # ===== 4. ЛОГ СЕРВЕРА =====
    print_section "4. DEEPSEEK СЕРВЕР (deepseek_server.log)"
    check_file "$LOG_DIR/deepseek_server.log" "$lines"
    
    # ===== 5. ОШИБКИ СЕРВИСА =====
    print_section "5. ОШИБКИ СЕРВИСА (service_error.log)"
    check_file "$LOG_DIR/service_error.log" "$lines"
    
    # ===== 6. СТАТУС СИСТЕМЫ =====
    print_section "6. СТАТУС ПРОЦЕССОВ"
    
    # Проверка моста
    if pgrep -f "email_bridge.py" > /dev/null; then
        PID=$(pgrep -f "email_bridge.py" | head -1)
        print_info "✅ Мост запущен (PID: $PID)"
        echo "   CPU: $(ps -p $PID -o %cpu= 2>/dev/null | xargs)%"
        echo "   RAM: $(ps -p $PID -o %mem= 2>/dev/null | xargs)%"
        echo "   Время работы: $(ps -p $PID -o etime= 2>/dev/null | xargs)"
        echo "   Время запуска: $(ps -p $PID -o lstart= 2>/dev/null | xargs)" 
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
        echo "   Время запуска: $(ps -p $PID -o lstart= 2>/dev/null | xargs)" 
    else
        print_error "❌ Сервер НЕ ЗАПУЩЕН"
    fi
    
    echo ""
    
    # ===== 7. ПОСЛЕДНИЕ ОШИБКИ =====
    print_section "7. ПОСЛЕДНИЕ ОШИБКИ В ЛОГАХ"
    
    echo -e "${BLUE}Ошибки в логе моста:${NC}"
    grep -i "error\|fail\|exception" "$LOG_DIR/deepseek_bridge_$DATE.log" 2>/dev/null | tail -5 | sed 's/^/  /' || echo "  (нет ошибок)"
    
    echo ""
    
    echo -e "${BLUE}Ошибки в логе сервера:${NC}"
    grep -i "error\|fail\|exception" "$LOG_DIR/deepseek_server.log" 2>/dev/null | tail -5 | sed 's/^/  /' || echo "  (нет ошибок)"
    
    echo ""
    
    # ===== 8. ПОСЛЕДНЯЯ ПРОВЕРКА ПОЧТЫ =====
    print_section "8. ПОСЛЕДНЯЯ ПРОВЕРКА ПОЧТЫ"
    
    LAST_CHECK=$(grep "Проверка почты" "$LOG_DIR/deepseek_bridge_$DATE.log" 2>/dev/null | tail -1)
    if [ -n "$LAST_CHECK" ]; then
        echo -e "${GREEN}✅ Последняя проверка:${NC}"
        echo "  $LAST_CHECK"
    else
        echo -e "${RED}❌ Нет записей о проверке почты${NC}"
    fi
    
    echo ""
    
    # ===== 9. ПОСЛЕДНИЕ ОТВЕТЫ =====
    print_section "9. ПОСЛЕДНИЕ ОТВЕТЫ (обработанные письма)"
    
    grep "✅ Получен ответ" "$LOG_DIR/deepseek_bridge_$DATE.log" 2>/dev/null | tail -3 | sed 's/^/  /' || echo "  (нет ответов)"
    
    echo ""
    
    # ===== 10. ИТОГ =====
    print_section "10. ИТОГ"
    
    if pgrep -f "email_bridge.py" > /dev/null && pgrep -f "app.py" > /dev/null; then
        echo -e "${GREEN}✅ ВСЕ ПРОЦЕССЫ РАБОТАЮТ${NC}"
    else
        echo -e "${RED}❌ НЕ ВСЕ ПРОЦЕССЫ ЗАПУЩЕНЫ${NC}"
        echo "   Запустите: ./scripts/01_run___server_and_client____run_all.sh"
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
        echo -e "${BLUE}📡 Режим наблюдения (обновление каждые 5 сек, Ctrl+C для выхода)${NC}"
        while true; do
            clear
            check_logs "$LINES"
            echo -e "${YELLOW}Обновление каждые 5 секунд...${NC}"
            sleep 5
        done
        ;;
    -e|--errors)
        print_header
        print_section "ОШИБКИ В ЛОГАХ"
        echo -e "${BLUE}Лог моста:${NC}"
        grep -i "error\|fail\|exception" "$LOG_DIR/deepseek_bridge_$(date +%Y%m%d).log" 2>/dev/null | tail -20 | sed 's/^/  /' || echo "  (нет ошибок)"
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
        echo "  -f, --follow     - режим наблюдения (обновление каждые 5 сек)"
        echo "  -e, --errors     - показать только ошибки"
        echo "  -h, --help       - показать эту справку"
        echo ""
        echo "Примеры:"
        echo "  $0               - проверить логи (10 строк)"
        echo "  $0 -n 20         - проверить логи (20 строк)"
        echo "  $0 -f            - следить за логами"
        echo "  $0 -e            - показать только ошибки"
        echo ""
        ;;
    *)
        check_logs "$LINES"
        ;;
esac