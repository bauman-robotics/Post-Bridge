#!/bin/bash
# -*- coding: utf-8 -*-

# ============================================
# ЗАПУСК DEEPSEEK API СЕРВЕРА
# ============================================

# Цвета
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

print_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
print_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
print_error() { echo -e "${RED}[ERROR]${NC} $1"; }
print_header() { echo -e "${BLUE}============================================${NC}"; }

# ============================================
# КОНФИГУРАЦИЯ
# ============================================

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_DIR="$PROJECT_DIR/venv"
DEEPSEEK_API_DIR="$PROJECT_DIR/Deepseek-API"
DEEPSEEK_SERVER_PORT=8000
SERVER_STARTUP_WAIT=10

LOG_DIR="$PROJECT_DIR/logs"
SERVER_LOG="$LOG_DIR/deepseek_server.log"
PID_DIR="$PROJECT_DIR/pids"
SERVER_PID_FILE="$PID_DIR/deepseek_server.pid"

# ============================================
# ФУНКЦИИ
# ============================================

create_dirs() {
    mkdir -p "$LOG_DIR" "$PID_DIR"
}

check_port() {
    if netstat -tuln 2>/dev/null | grep -q ":$1 "; then
        return 0  # Порт занят
    else
        return 1  # Порт свободен
    fi
}

check_server_health() {
    if curl -s -f "http://localhost:$1/healthz" > /dev/null 2>&1; then
        return 0
    else
        return 1
    fi
}

find_server_pid() {
    local pid=$(ps aux | grep -E "python.*app\.py" | grep -v grep | awk '{print $2}' | head -1)
    if [ -n "$pid" ]; then
        echo "$pid"
        return 0
    else
        return 1
    fi
}

# ============================================
# ОСНОВНАЯ ФУНКЦИЯ
# ============================================

start_server() {
    print_header
    echo "  🚀 ЗАПУСК DEEPSEEK API СЕРВЕРА"
    print_header
    
    # Проверяем venv
    if [ ! -d "$VENV_DIR" ]; then
        print_error "Виртуальное окружение не найдено: $VENV_DIR"
        exit 1
    fi
    
    create_dirs
    
    # Проверяем, не запущен ли уже сервер
    print_info "Проверка порта $DEEPSEEK_SERVER_PORT..."
    
    if check_port "$DEEPSEEK_SERVER_PORT"; then
        print_warn "⚠️  Порт $DEEPSEEK_SERVER_PORT уже занят!"
        
        if check_server_health "$DEEPSEEK_SERVER_PORT"; then
            print_info "✅ Сервер уже запущен и работает"
            local pid=$(find_server_pid)
            if [ -n "$pid" ]; then
                echo "$pid" > "$SERVER_PID_FILE"
                print_info "   PID: $pid"
            fi
            return 0
        else
            print_warn "⚠️  Порт занят, но сервер не отвечает"
            local pid=$(find_server_pid)
            if [ -n "$pid" ]; then
                print_info "   Найден процесс (PID: $pid), перезапускаю..."
                kill -9 "$pid" 2>/dev/null
                sleep 2
            else
                print_error "   Процесс не найден, но порт занят"
                print_info "   Проверьте вручную: sudo lsof -i :$DEEPSEEK_SERVER_PORT"
                exit 1
            fi
        fi
    fi
    
    # Проверяем наличие папки с сервером
    if [ ! -d "$DEEPSEEK_API_DIR" ]; then
        print_error "Папка с DeepSeek API не найдена: $DEEPSEEK_API_DIR"
        exit 1
    fi
    
    if [ ! -f "$DEEPSEEK_API_DIR/app.py" ]; then
        print_error "app.py не найден в $DEEPSEEK_API_DIR"
        exit 1
    fi
    
    # Запускаем сервер
    print_info "🚀 Запуск DeepSeek API сервера..."
    print_info "   📁 Папка: $DEEPSEEK_API_DIR"
    print_info "   🔌 Порт: $DEEPSEEK_SERVER_PORT"
    print_info "   📄 Лог: $SERVER_LOG"
    
    source "$VENV_DIR/bin/activate"
    cd "$DEEPSEEK_API_DIR" || exit 1
    
    nohup python app.py > "$SERVER_LOG" 2>&1 &
    local pid=$!
    echo $pid > "$SERVER_PID_FILE"
    
    cd "$PROJECT_DIR" || exit 1
    deactivate
    
    print_info "   PID: $pid"
    print_info "⏳ Ожидание запуска ($SERVER_STARTUP_WAIT сек)..."
    
    local counter=0
    while [ $counter -lt "$SERVER_STARTUP_WAIT" ]; do
        if check_server_health "$DEEPSEEK_SERVER_PORT"; then
            print_info "✅ Сервер успешно запущен на порту $DEEPSEEK_SERVER_PORT!"
            return 0
        fi
        sleep 1
        counter=$((counter + 1))
        echo -ne "\r   ⏳ Ожидание... $counter/$SERVER_STARTUP_WAIT сек"
    done
    echo ""
    
    # Проверяем, жив ли процесс
    if kill -0 "$pid" 2>/dev/null; then
        print_warn "⚠️  Сервер запущен, но не отвечает на health-запрос"
        print_info "   Проверьте лог: tail -f $SERVER_LOG"
        return 0
    else
        print_error "❌ Не удалось запустить сервер"
        print_info "   Проверьте лог: cat $SERVER_LOG"
        return 1
    fi
}

# ============================================
# ЗАПУСК
# ============================================

case "$1" in
    stop)
        print_header
        echo "  🛑 ОСТАНОВКА СЕРВЕРА"
        print_header
        
        if [ -f "$SERVER_PID_FILE" ]; then
            local pid=$(cat "$SERVER_PID_FILE")
            if kill -0 "$pid" 2>/dev/null; then
                print_info "Остановка сервера (PID: $pid)..."
                kill "$pid"
                sleep 2
                if kill -0 "$pid" 2>/dev/null; then
                    print_warn "Принудительная остановка..."
                    kill -9 "$pid"
                fi
                rm -f "$SERVER_PID_FILE"
                print_info "✅ Сервер остановлен"
            else
                print_warn "Процесс не запущен"
                rm -f "$SERVER_PID_FILE"
            fi
        else
            print_warn "PID файл не найден"
            local pid=$(ps aux | grep -E "python.*app\.py" | grep -v grep | awk '{print $2}')
            if [ -n "$pid" ]; then
                print_info "Найден процесс (PID: $pid), останавливаю..."
                kill "$pid" 2>/dev/null
                print_info "✅ Сервер остановлен"
            else
                print_info "Сервер не запущен"
            fi
        fi
        ;;
    
    status)
        print_header
        echo "  📊 СТАТУС СЕРВЕРА"
        print_header
        
        if check_port "$DEEPSEEK_SERVER_PORT"; then
            echo -e "${YELLOW}🔍 Порт $DEEPSEEK_SERVER_PORT: ЗАНЯТ${NC}"
        else
            echo -e "${GREEN}🔍 Порт $DEEPSEEK_SERVER_PORT: СВОБОДЕН${NC}"
        fi
        
        local pid=$(find_server_pid)
        if [ -n "$pid" ]; then
            echo -e "${GREEN}✅ Сервер запущен (PID: $pid)${NC}"
            if check_server_health "$DEEPSEEK_SERVER_PORT"; then
                echo -e "   ${GREEN}✅ Health: OK${NC}"
            else
                echo -e "   ${RED}❌ Health: FAIL${NC}"
            fi
            echo "$pid" > "$SERVER_PID_FILE"
        else
            echo -e "${RED}❌ Сервер не запущен${NC}"
        fi
        ;;
    
    logs)
        echo -e "${BLUE}=== ЛОГ СЕРВЕРА (tail -f) ===${NC}"
        tail -f "$SERVER_LOG"
        ;;
    
    help|--help|-h)
        echo ""
        echo "Использование: $0 {start|stop|status|logs|help}"
        echo ""
        echo "  start   - Запустить сервер"
        echo "  stop    - Остановить сервер"
        echo "  status  - Проверить статус"
        echo "  logs    - Просмотреть лог (tail -f)"
        echo "  help    - Показать эту справку"
        echo ""
        echo "Порт: $DEEPSEEK_SERVER_PORT"
        echo "Лог: $SERVER_LOG"
        echo ""
        ;;
    
    *)
        # Если нет аргументов - запускаем сервер
        start_server
        ;;
esac