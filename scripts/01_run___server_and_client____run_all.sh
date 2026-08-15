#!/bin/bash
# -*- coding: utf-8 -*-

# ./01_run.sh

# Проверка статуса 
# ./01_run.sh status


# ============================================
# ЗАПУСК ПОЧТОВОГО МОСТА DEEPSEEK
# ============================================

# Цвета
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# ============================================
# КОНФИГУРАЦИЯ
# ============================================

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
VENV_DIR="$PROJECT_DIR/venv"
DEEPSEEK_API_DIR="$PROJECT_DIR/Deepseek-API"
BRIDGE_SCRIPT="$PROJECT_DIR/src/email_bridge.py"
DEEPSEEK_SERVER_PORT=8001
SERVER_STARTUP_WAIT=10
BRIDGE_MODE="server"

LOG_DIR="$PROJECT_DIR/logs"
SERVER_LOG="$LOG_DIR/deepseek_server.log"
BRIDGE_LOG="$LOG_DIR/bridge.log"
PID_DIR="$PROJECT_DIR/pids"
SERVER_PID_FILE="$PID_DIR/deepseek_server.pid"
BRIDGE_PID_FILE="$PID_DIR/bridge.pid"

# ============================================
# ФУНКЦИИ
# ============================================

print_header() {
    echo -e "${BLUE}"
    echo "============================================"
    echo "  🚀 ПОЧТОВЫЙ МОСТ DEEPSEEK"
    echo "============================================"
    echo -e "${NC}"
}

print_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
print_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
print_error() { echo -e "${RED}[ERROR]${NC} $1"; }

check_venv() {
    if [ ! -d "$VENV_DIR" ]; then
        print_error "Виртуальное окружение не найдено: $VENV_DIR"
        exit 1
    fi
}

check_dependencies() {
    print_info "Проверка зависимостей..."
    source "$VENV_DIR/bin/activate"
    local missing_packages=()
    
    for pkg in pyyaml requests; do
        if ! python -c "import $pkg" 2>/dev/null; then
            missing_packages+=("$pkg")
        fi
    done
    
    if [ ${#missing_packages[@]} -gt 0 ]; then
        print_warn "Отсутствуют пакеты: ${missing_packages[*]}"
        pip install "${missing_packages[@]}"
    fi
    
    deactivate
}

create_dirs() {
    mkdir -p "$LOG_DIR" "$PID_DIR"
}

check_port() {
    # Проверяем, занят ли порт
    print_info "   Диагностика: проверяю порт $1..."
    
    # Способ 1: netstat
    if netstat -tuln 2>/dev/null | grep -q ":$1 "; then
        print_info "   netstat: порт $1 ЗАНЯТ"
        return 0
    fi
    
    # Способ 2: ss (если netstat нет)
    if ss -tuln 2>/dev/null | grep -q ":$1 "; then
        print_info "   ss: порт $1 ЗАНЯТ"
        return 0
    fi
    
    print_info "   порт $1 СВОБОДЕН"
    return 1
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

find_bridge_pid() {
    local pid=$(ps aux | grep -E "python.*email_bridge\.py" | grep -v grep | awk '{print $2}' | head -1)
    if [ -n "$pid" ]; then
        echo "$pid"
        return 0
    else
        return 1
    fi
}

kill_process() {
    local pid_file=$1
    local process_name=$2
    
    if [ -f "$pid_file" ]; then
        local pid=$(cat "$pid_file")
        if kill -0 "$pid" 2>/dev/null; then
            print_info "Остановка $process_name (PID: $pid)..."
            kill "$pid"
            sleep 2
            if kill -0 "$pid" 2>/dev/null; then
                print_warn "Принудительная остановка $process_name..."
                kill -9 "$pid"
            fi
            rm -f "$pid_file"
            print_info "✅ $process_name остановлен"
        else
            rm -f "$pid_file"
        fi
    fi
}

check_and_start_server() {
    print_info "Проверка DeepSeek API сервера на порту $DEEPSEEK_SERVER_PORT..."
    
    # ===== ДИАГНОСТИКА: проверяем порт =====
    print_info "   Диагностика: запускаю проверку порта..."
    
    if check_port "$DEEPSEEK_SERVER_PORT"; then
        print_warn "⚠️  Порт $DEEPSEEK_SERVER_PORT уже занят!"
        
        # Проверяем, отвечает ли сервер
        if check_server_health "$DEEPSEEK_SERVER_PORT"; then
            print_info "✅ Сервер уже запущен и работает (порт $DEEPSEEK_SERVER_PORT)"
            local pid=$(find_server_pid)
            if [ -n "$pid" ]; then
                echo "$pid" > "$SERVER_PID_FILE"
                print_info "   PID: $pid (сохранен)"
            fi
            return 0
        else
            print_warn "⚠️  Порт занят, но сервер не отвечает"
            
            local pid=$(find_server_pid)
            if [ -n "$pid" ]; then
                print_info "   Найден процесс python app.py (PID: $pid)"
                print_info "   🔄 Перезапускаю сервер..."
                kill -9 "$pid" 2>/dev/null
                sleep 2
            else
                print_error "   ❌ Процесс не найден, но порт занят"
                print_info "   Проверьте вручную:"
                print_info "     sudo netstat -tulpn | grep $DEEPSEEK_SERVER_PORT"
                print_info "     sudo lsof -i :$DEEPSEEK_SERVER_PORT"
                return 1
            fi
        fi
    fi
    
    # ===== Порт свободен - запускаем =====
    print_info "🚀 Запуск DeepSeek API сервера на порту $DEEPSEEK_SERVER_PORT..."
    
    if [ ! -d "$DEEPSEEK_API_DIR" ]; then
        print_error "Папка с DeepSeek API не найдена: $DEEPSEEK_API_DIR"
        return 1
    fi
    
    if [ ! -f "$DEEPSEEK_API_DIR/app.py" ]; then
        print_error "app.py не найден в $DEEPSEEK_API_DIR"
        return 1
    fi
    
    print_info "   📁 Папка: $DEEPSEEK_API_DIR"
    print_info "   🔌 Порт: $DEEPSEEK_SERVER_PORT"
    print_info "   📄 Лог: $SERVER_LOG"
    
    source "$VENV_DIR/bin/activate"
    cd "$DEEPSEEK_API_DIR" || exit 1
    
    nohup python app.py > "$SERVER_LOG" 2>&1 &
    local new_pid=$!
    echo $new_pid > "$SERVER_PID_FILE"
    
    cd "$PROJECT_DIR" || exit 1
    deactivate
    
    print_info "   PID: $new_pid"
    print_info "⏳ Ожидание запуска сервера ($SERVER_STARTUP_WAIT сек)..."
    
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
    
    if kill -0 "$new_pid" 2>/dev/null; then
        print_warn "⚠️  Сервер запущен, но не отвечает на health-запрос"
        print_info "   Проверьте лог: tail -f $SERVER_LOG"
        return 0
    else
        print_error "❌ Не удалось запустить сервер"
        print_info "   Проверьте лог: cat $SERVER_LOG"
        return 1
    fi
}

start_bridge() {
    local existing_pid=$(find_bridge_pid)
    if [ -n "$existing_pid" ]; then
        print_warn "⚠️  Почтовый мост уже запущен (PID: $existing_pid)"
        echo "$existing_pid" > "$BRIDGE_PID_FILE"
        print_info "   Использую существующий процесс"
        return 0
    fi
    
    print_info "🚀 Запуск почтового моста..."
    print_info "   📄 Лог: $BRIDGE_LOG"
    
    if [ ! -f "$BRIDGE_SCRIPT" ]; then
        print_error "email_bridge.py не найден в $PROJECT_DIR"
        return 1
    fi
    
    source "$VENV_DIR/bin/activate"
    cd "$PROJECT_DIR" || exit 1
    
    local cmd="python $BRIDGE_SCRIPT"
    if [ "$BRIDGE_MODE" == "once" ]; then
        cmd="$cmd --once"
    elif [ "$BRIDGE_MODE" == "batch" ]; then
        cmd="$cmd --batch"
    fi
    
    nohup $cmd > "$BRIDGE_LOG" 2>&1 &
    local pid=$!
    echo $pid > "$BRIDGE_PID_FILE"
    
    deactivate
    
    print_info "   PID: $pid"
    print_info "✅ Почтовый мост запущен!"
    print_info "   📄 Лог: tail -f $BRIDGE_LOG"
}

stop_all() {
    print_info "🛑 Остановка всех процессов..."
    kill_process "$SERVER_PID_FILE" "DeepSeek сервер"
    kill_process "$BRIDGE_PID_FILE" "почтовый мост"
    print_info "✅ Все процессы остановлены"
}

status() {
    echo ""
    echo "============================================"
    echo "  📊 СТАТУС ПРОЦЕССОВ"
    echo "============================================"
    
    if check_port "$DEEPSEEK_SERVER_PORT"; then
        echo -e "\n🔍 Порт $DEEPSEEK_SERVER_PORT: ${YELLOW}ЗАНЯТ${NC}"
    else
        echo -e "\n🔍 Порт $DEEPSEEK_SERVER_PORT: ${GREEN}СВОБОДЕН${NC}"
    fi
    
    local server_pid=$(find_server_pid)
    if [ -n "$server_pid" ]; then
        echo -e "\n${GREEN}✅ DeepSeek сервер:${NC} запущен (PID: $server_pid)"
        if check_server_health "$DEEPSEEK_SERVER_PORT"; then
            echo -e "   ${GREEN}✅ Health: OK${NC}"
        else
            echo -e "   ${RED}❌ Health: FAIL${NC}"
        fi
        echo "$server_pid" > "$SERVER_PID_FILE"
    else
        echo -e "\n${RED}❌ DeepSeek сервер:${NC} не запущен"
    fi
    
    local bridge_pid=$(find_bridge_pid)
    if [ -n "$bridge_pid" ]; then
        echo -e "\n${GREEN}✅ Почтовый мост:${NC} запущен (PID: $bridge_pid)"
        echo "$bridge_pid" > "$BRIDGE_PID_FILE"
    else
        echo -e "\n${RED}❌ Почтовый мост:${NC} не запущен"
    fi
    
    echo ""
    echo "============================================"
}

show_logs() {
    local service=$1
    if [ "$service" == "server" ] || [ -z "$service" ]; then
        echo -e "${BLUE}=== ЛОГ СЕРВЕРА (tail -f) ===${NC}"
        tail -f "$SERVER_LOG"
    elif [ "$service" == "bridge" ]; then
        echo -e "${BLUE}=== ЛОГ МОСТА (tail -f) ===${NC}"
        tail -f "$BRIDGE_LOG"
    else
        echo "Использование: $0 logs [server|bridge]"
    fi
}

# ============================================
# ОСНОВНОЙ СКРИПТ
# ============================================

case "$1" in
    start)
        print_header
        check_venv
        check_dependencies
        create_dirs
        if check_and_start_server; then
            start_bridge
        else
            print_error "Не удалось запустить сервер. Мост не запущен."
            exit 1
        fi
        ;;
    
    stop)
        print_header
        stop_all
        ;;
    
    restart)
        print_header
        stop_all
        sleep 2
        check_venv
        check_dependencies
        create_dirs
        if check_and_start_server; then
            start_bridge
        else
            print_error "Не удалось запустить сервер. Мост не запущен."
            exit 1
        fi
        ;;
    
    status)
        status
        ;;
    
    logs)
        show_logs "$2"
        ;;
    
    once)
        print_header
        check_venv
        check_dependencies
        create_dirs
        if ! check_server_health "$DEEPSEEK_SERVER_PORT"; then
            print_error "Сервер не запущен или не отвечает!"
            print_info "Запустите: ./01_run.sh start"
            exit 1
        fi
        BRIDGE_MODE="once"
        start_bridge
        if [ -f "$BRIDGE_PID_FILE" ]; then
            local pid=$(cat "$BRIDGE_PID_FILE")
            wait "$pid" 2>/dev/null
            print_info "✅ Одноразовая обработка завершена"
        fi
        ;;
    
    kill-server)
        print_header
        print_info "Принудительная остановка сервера..."
        local pid=$(find_server_pid)
        if [ -n "$pid" ]; then
            print_info "Убиваю процесс PID: $pid"
            kill -9 "$pid" 2>/dev/null
            rm -f "$SERVER_PID_FILE"
            print_info "✅ Сервер остановлен"
        else
            print_warn "Сервер не найден"
        fi
        ;;
    
    kill-bridge)
        print_header
        print_info "Принудительная остановка моста..."
        local pid=$(find_bridge_pid)
        if [ -n "$pid" ]; then
            print_info "Убиваю процесс PID: $pid"
            kill -9 "$pid" 2>/dev/null
            rm -f "$BRIDGE_PID_FILE"
            print_info "✅ Мост остановлен"
        else
            print_warn "Мост не найден"
        fi
        ;;
    
    kill-all)
        print_header
        print_info "Принудительная остановка всех процессов..."
        local pid=$(find_server_pid)
        if [ -n "$pid" ]; then
            print_info "Убиваю сервер PID: $pid"
            kill -9 "$pid" 2>/dev/null
        fi
        local pid2=$(find_bridge_pid)
        if [ -n "$pid2" ]; then
            print_info "Убиваю мост PID: $pid2"
            kill -9 "$pid2" 2>/dev/null
        fi
        rm -f "$SERVER_PID_FILE" "$BRIDGE_PID_FILE"
        print_info "✅ Все процессы остановлены"
        ;;
    
    help|--help|-h)
        echo ""
        echo "Использование: $0 {start|stop|restart|status|logs|once|kill-server|kill-bridge|kill-all|help}"
        echo ""
        echo "  start         - Запуск всех сервисов"
        echo "  stop          - Остановка всех сервисов"
        echo "  restart       - Перезапуск всех сервисов"
        echo "  status        - Проверка статуса"
        echo "  logs          - Просмотр логов (server или bridge)"
        echo "  once          - Одноразовая обработка"
        echo "  kill-server   - Принудительное убийство сервера"
        echo "  kill-bridge   - Принудительное убийство моста"
        echo "  kill-all      - Принудительное убийство всех процессов"
        echo "  help          - Показать эту справку"
        echo ""
        echo "Текущий порт: $DEEPSEEK_SERVER_PORT"
        echo ""
        ;;
    
    *)
        print_header
        check_venv
        check_dependencies
        create_dirs
        if check_and_start_server; then
            start_bridge
        else
            print_error "Не удалось запустить сервер. Мост не запущен."
            exit 1
        fi
        ;;
esac