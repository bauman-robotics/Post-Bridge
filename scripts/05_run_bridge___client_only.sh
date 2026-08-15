#!/bin/bash
# -*- coding: utf-8 -*-

# ============================================
# ЗАПУСК ПОЧТОВОГО МОСТА (КЛИЕНТА)
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
BRIDGE_SCRIPT="$PROJECT_DIR/src/email_bridge.py"
DEEPSEEK_SERVER_PORT=8001
BRIDGE_MODE="server"  # server или once

LOG_DIR="$PROJECT_DIR/logs"
BRIDGE_LOG="$LOG_DIR/bridge.log"
PID_DIR="$PROJECT_DIR/pids"
BRIDGE_PID_FILE="$PID_DIR/bridge.pid"

# ============================================
# ФУНКЦИИ
# ============================================

create_dirs() {
    mkdir -p "$LOG_DIR" "$PID_DIR"
}

check_server_health() {
    if curl -s -f "http://localhost:$1/healthz" > /dev/null 2>&1; then
        return 0
    else
        return 1
    fi
}

check_port() {
    if netstat -tuln 2>/dev/null | grep -q ":$1 "; then
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

find_bridge_pid() {
    local pid=$(ps aux | grep -E "python.*email_bridge\.py" | grep -v grep | awk '{print $2}' | head -1)
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

start_bridge() {
    print_header
    echo "  🚀 ЗАПУСК ПОЧТОВОГО МОСТА (КЛИЕНТА)"
    print_header
    
    # Проверяем venv
    if [ ! -d "$VENV_DIR" ]; then
        print_error "Виртуальное окружение не найдено: $VENV_DIR"
        exit 1
    fi
    
    create_dirs
    
    # Проверяем, что сервер запущен
    print_info "Проверка DeepSeek API сервера..."
    
    # Сначала проверяем health
    if check_server_health "$DEEPSEEK_SERVER_PORT"; then
        print_info "✅ Сервер работает (порт $DEEPSEEK_SERVER_PORT)"
    else
        # Если health не отвечает, проверяем порт
        if check_port "$DEEPSEEK_SERVER_PORT"; then
            print_warn "⚠️  Порт $DEEPSEEK_SERVER_PORT занят, но сервер не отвечает"
            
            # Проверяем, есть ли процесс
            local pid=$(find_server_pid)
            if [ -n "$pid" ]; then
                print_info "   Найден процесс (PID: $pid), но он не отвечает"
                print_info "   Попробуйте перезапустить сервер: ./scripts/03_run_server_only.sh stop && ./scripts/03_run_server_only.sh start"
            else
                print_error "❌ Порт занят, но процесс не найден"
                print_info "   Проверьте: sudo lsof -i :$DEEPSEEK_SERVER_PORT"
            fi
            exit 1
        else
            print_error "❌ Сервер не запущен на порту $DEEPSEEK_SERVER_PORT!"
            print_info "   Запустите сервер: ./scripts/03_run_server_only.sh start"
            exit 1
        fi
    fi
    
    # Проверяем, не запущен ли уже мост
    local existing_pid=$(find_bridge_pid)
    if [ -n "$existing_pid" ]; then
        print_warn "⚠️  Почтовый мост уже запущен (PID: $existing_pid)"
        echo "$existing_pid" > "$BRIDGE_PID_FILE"
        print_info "   Использую существующий процесс"
        return 0
    fi
    
    # Проверяем наличие скрипта
    if [ ! -f "$BRIDGE_SCRIPT" ]; then
        print_error "email_bridge.py не найден в $PROJECT_DIR/src/"
        exit 1
    fi
    
    # Запускаем мост
    print_info "🚀 Запуск почтового моста..."
    print_info "   📄 Лог: $BRIDGE_LOG"
    
    source "$VENV_DIR/bin/activate"
    cd "$PROJECT_DIR" || exit 1
    
    local cmd="python $BRIDGE_SCRIPT"
    
    if [ "$BRIDGE_MODE" == "once" ]; then
        cmd="$cmd --once"
        print_info "   🔄 Режим: одноразовая проверка"
    else
        print_info "   🔄 Режим: постоянная работа"
    fi
    
    nohup $cmd > "$BRIDGE_LOG" 2>&1 &
    local pid=$!
    echo $pid > "$BRIDGE_PID_FILE"
    
    deactivate
    
    print_info "   PID: $pid"
    print_info "✅ Почтовый мост запущен!"
    print_info "   📄 Лог: tail -f $BRIDGE_LOG"
}

# ============================================
# ЗАПУСК
# ============================================

case "$1" in
    start|"")
        start_bridge
        ;;
    
    once)
        BRIDGE_MODE="once"
        start_bridge
        # Ждем завершения одноразового запуска
        if [ -f "$BRIDGE_PID_FILE" ]; then
            local pid=$(cat "$BRIDGE_PID_FILE")
            wait "$pid" 2>/dev/null
            print_info "✅ Одноразовая проверка завершена"
        fi
        ;;
    
    stop)
        print_header
        echo "  🛑 ОСТАНОВКА МОСТА"
        print_header
        
        if [ -f "$BRIDGE_PID_FILE" ]; then
            local pid=$(cat "$BRIDGE_PID_FILE")
            if kill -0 "$pid" 2>/dev/null; then
                print_info "Остановка моста (PID: $pid)..."
                kill "$pid"
                sleep 2
                if kill -0 "$pid" 2>/dev/null; then
                    print_warn "Принудительная остановка..."
                    kill -9 "$pid"
                fi
                rm -f "$BRIDGE_PID_FILE"
                print_info "✅ Мост остановлен"
            else
                print_warn "Процесс не запущен"
                rm -f "$BRIDGE_PID_FILE"
            fi
        else
            print_warn "PID файл не найден"
            local pid=$(find_bridge_pid)
            if [ -n "$pid" ]; then
                print_info "Найден процесс (PID: $pid), останавливаю..."
                kill "$pid" 2>/dev/null
                print_info "✅ Мост остановлен"
            else
                print_info "Мост не запущен"
            fi
        fi
        ;;
    
    status)
        print_header
        echo "  📊 СТАТУС МОСТА"
        print_header
        
        # Проверяем сервер
        if check_server_health "$DEEPSEEK_SERVER_PORT"; then
            echo -e "${GREEN}✅ Сервер: работает${NC} (порт $DEEPSEEK_SERVER_PORT)"
        else
            if check_port "$DEEPSEEK_SERVER_PORT"; then
                echo -e "${YELLOW}⚠️  Сервер: порт занят, но не отвечает${NC}"
            else
                echo -e "${RED}❌ Сервер: не запущен${NC}"
            fi
        fi
        
        # Проверяем мост
        local pid=$(find_bridge_pid)
        if [ -n "$pid" ]; then
            echo -e "${GREEN}✅ Мост: запущен (PID: $pid)${NC}"
            echo "$pid" > "$BRIDGE_PID_FILE"
        else
            echo -e "${RED}❌ Мост: не запущен${NC}"
        fi
        ;;
    
    logs)
        echo -e "${BLUE}=== ЛОГ МОСТА (tail -f) ===${NC}"
        tail -f "$BRIDGE_LOG"
        ;;
    
    help|--help|-h)
        echo ""
        echo "Использование: $0 {start|once|stop|status|logs|help}"
        echo ""
        echo "  start   - Запустить мост в режиме сервера (постоянно)"
        echo "  once    - Запустить мост один раз (проверить почту и завершиться)"
        echo "  stop    - Остановить мост"
        echo "  status  - Проверить статус"
        echo "  logs    - Просмотреть лог (tail -f)"
        echo "  help    - Показать эту справку"
        echo ""
        echo "Требования:"
        echo "  - Сервер должен быть запущен (./scripts/03_run_server_only.sh start)"
        echo "  - Конфиг: config/config.yaml и config/secrets.yaml"
        echo ""
        echo "Порт: $DEEPSEEK_SERVER_PORT"
        echo "Лог: $BRIDGE_LOG"
        echo ""
        ;;
    
    *)
        print_error "Неизвестная команда: $1"
        echo "Используйте: $0 help"
        exit 1
        ;;
esac