#!/bin/bash
# -*- coding: utf-8 -*-

# ============================================
# ПРОВЕРКА СТАТУСА ВСЕХ КОМПОНЕНТОВ
# ============================================

# Цвета
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
MAGENTA='\033[0;35m'
CYAN='\033[0;36m'
NC='\033[0m'

# ============================================
# КОНФИГУРАЦИЯ
# ============================================

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEEPSEEK_SERVER_PORT=8000
LOG_DIR="$PROJECT_DIR/logs"
PID_DIR="$PROJECT_DIR/pids"
SERVER_PID_FILE="$PID_DIR/deepseek_server.pid"
BRIDGE_PID_FILE="$PID_DIR/bridge.pid"
SERVER_LOG="$LOG_DIR/deepseek_server.log"
BRIDGE_LOG="$LOG_DIR/bridge.log"

# ============================================
# ФУНКЦИИ
# ============================================

print_header() {
    echo ""
    echo -e "${BLUE}╔══════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${BLUE}║${NC}  ${CYAN}🔍 СТАТУС ВСЕХ КОМПОНЕНТОВ${NC}                              ${BLUE}║${NC}"
    echo -e "${BLUE}╚══════════════════════════════════════════════════════════════╝${NC}"
    echo ""
}

print_section() {
    echo -e "${MAGENTA}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${CYAN}  $1${NC}"
    echo -e "${MAGENTA}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
}

print_ok() { echo -e "  ${GREEN}✅${NC} $1"; }
print_warn() { echo -e "  ${YELLOW}⚠️${NC}  $1"; }
print_error() { echo -e "  ${RED}❌${NC} $1"; }
print_info() { echo -e "  ${BLUE}ℹ️${NC}  $1"; }

check_port() {
    if netstat -tuln 2>/dev/null | grep -q ":$1 "; then
        return 0
    else
        return 1
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

find_bridge_pid() {
    local pid=$(ps aux | grep -E "python.*email_bridge\.py" | grep -v grep | awk '{print $2}' | head -1)
    if [ -n "$pid" ]; then
        echo "$pid"
        return 0
    else
        return 1
    fi
}

get_process_uptime() {
    local pid=$1
    if [ -n "$pid" ]; then
        local uptime=$(ps -p "$pid" -o etime= 2>/dev/null | xargs)
        if [ -n "$uptime" ]; then
            echo "$uptime"
        else
            echo "N/A"
        fi
    else
        echo "N/A"
    fi
}

get_process_cpu() {
    local pid=$1
    if [ -n "$pid" ]; then
        local cpu=$(ps -p "$pid" -o %cpu= 2>/dev/null | xargs)
        if [ -n "$cpu" ]; then
            echo "$cpu%"
        else
            echo "N/A"
        fi
    else
        echo "N/A"
    fi
}

get_process_memory() {
    local pid=$1
    if [ -n "$pid" ]; then
        local mem=$(ps -p "$pid" -o %mem= 2>/dev/null | xargs)
        if [ -n "$mem" ]; then
            echo "$mem%"
        else
            echo "N/A"
        fi
    else
        echo "N/A"
    fi
}

get_log_tail() {
    local log_file=$1
    local lines=${2:-3}
    if [ -f "$log_file" ]; then
        tail -"$lines" "$log_file" 2>/dev/null | sed 's/^/      /'
    else
        echo "      (лог не найден)"
    fi
}

get_timestamp() {
    date '+%Y-%m-%d %H:%M:%S'
}

# ============================================
# ОСНОВНАЯ ФУНКЦИЯ
# ============================================

check_all() {
    print_header
    
    local timestamp=$(get_timestamp)
    echo -e "  ${BLUE}📅 Время проверки:${NC} $timestamp"
    echo ""
    
    # ===== 1. ПРОВЕРКА СЕРВЕРА =====
    print_section "1. DEEPSEEK API СЕРВЕР"
    
    local server_pid=$(find_server_pid)
    local port_busy=false
    local health_ok=false
    
    if check_port "$DEEPSEEK_SERVER_PORT"; then
        port_busy=true
        print_info "Порт $DEEPSEEK_SERVER_PORT: ${YELLOW}ЗАНЯТ${NC}"
    else
        print_info "Порт $DEEPSEEK_SERVER_PORT: ${GREEN}СВОБОДЕН${NC}"
    fi
    
    if check_server_health "$DEEPSEEK_SERVER_PORT"; then
        health_ok=true
        print_ok "Health-check: ${GREEN}OK${NC}"
    else
        print_error "Health-check: ${RED}FAIL${NC}"
    fi
    
    if [ -n "$server_pid" ]; then
        local uptime=$(get_process_uptime "$server_pid")
        local cpu=$(get_process_cpu "$server_pid")
        local mem=$(get_process_memory "$server_pid")
        
        echo ""
        print_ok "Процесс запущен"
        print_info "  PID: ${GREEN}$server_pid${NC}"
        print_info "  Время работы: $uptime"
        print_info "  CPU: $cpu | RAM: $mem"
        
        # Сохраняем PID
        echo "$server_pid" > "$SERVER_PID_FILE" 2>/dev/null
    else
        echo ""
        if [ "$port_busy" = true ] && [ "$health_ok" = false ]; then
            print_warn "Порт занят, но процесс не найден или не отвечает"
            print_info "  Возможно, это другой процесс"
            print_info "  Проверьте: sudo lsof -i :$DEEPSEEK_SERVER_PORT"
        elif [ "$port_busy" = false ]; then
            print_error "Сервер НЕ ЗАПУЩЕН"
            print_info "  Запустите: ./scripts/03_start_server.sh start"
        fi
    fi
    
    # Показываем последние строки лога сервера
    echo ""
    print_info "Последние строки лога сервера:"
    get_log_tail "$SERVER_LOG" 2
    
    # ===== 2. ПРОВЕРКА МОСТА =====
    echo ""
    print_section "2. ПОЧТОВЫЙ МОСТ (КЛИЕНТ)"
    
    local bridge_pid=$(find_bridge_pid)
    
    # Проверяем, запущен ли мост
    if [ -n "$bridge_pid" ]; then
        local uptime=$(get_process_uptime "$bridge_pid")
        local cpu=$(get_process_cpu "$bridge_pid")
        local mem=$(get_process_memory "$bridge_pid")
        
        print_ok "Процесс запущен"
        print_info "  PID: ${GREEN}$bridge_pid${NC}"
        print_info "  Время работы: $uptime"
        print_info "  CPU: $cpu | RAM: $mem"
        
        # Сохраняем PID
        echo "$bridge_pid" > "$BRIDGE_PID_FILE" 2>/dev/null
    else
        print_error "Мост НЕ ЗАПУЩЕН"
        print_info "  Запустите: ./scripts/04_start_bridge.sh start"
    fi
    
    # Показываем последние строки лога моста
    echo ""
    print_info "Последние строки лога моста:"
    get_log_tail "$BRIDGE_LOG" 2
    
    # ===== 3. СВОДКА =====
    echo ""
    print_section "3. СВОДКА"
    
    local all_ok=true
    
    # Сервер
    if [ -n "$server_pid" ] && [ "$health_ok" = true ]; then
        echo -e "  ${GREEN}✅ Сервер:${NC} работает (PID: $server_pid)"
    elif [ -n "$server_pid" ] && [ "$health_ok" = false ]; then
        echo -e "  ${YELLOW}⚠️  Сервер:${NC} запущен, но не отвечает (PID: $server_pid)"
        all_ok=false
    else
        echo -e "  ${RED}❌ Сервер:${NC} не запущен"
        all_ok=false
    fi
    
    # Мост
    if [ -n "$bridge_pid" ]; then
        echo -e "  ${GREEN}✅ Мост:${NC} работает (PID: $bridge_pid)"
    else
        echo -e "  ${RED}❌ Мост:${NC} не запущен"
        all_ok=false
    fi
    
    # Итог
    echo ""
    echo -e "${MAGENTA}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    if [ "$all_ok" = true ]; then
        echo -e "  ${GREEN}✅ ВСЕ КОМПОНЕНТЫ РАБОТАЮТ!${NC}"
    else
        echo -e "  ${YELLOW}⚠️  НЕ ВСЕ КОМПОНЕНТЫ ЗАПУЩЕНЫ${NC}"
        echo -e "  ${BLUE}ℹ️  Запустите всё: ./scripts/01_run.sh start${NC}"
    fi
    echo -e "${MAGENTA}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo ""
}

# ============================================
# ЗАПУСК
# ============================================

case "$1" in
    --watch|-w)
        # Режим наблюдения (обновляется каждые 5 секунд)
        while true; do
            clear
            check_all
            echo -e "${BLUE}Нажмите Ctrl+C для выхода (обновление каждые 5 сек)${NC}"
            sleep 5
        done
        ;;
    
    --json|-j)
        # Вывод в JSON формате (для автоматизации)
        echo "{"
        echo "  \"timestamp\": \"$(date -Iseconds)\","
        echo "  \"server\": {"
        echo "    \"pid\": \"$(find_server_pid)\","
        echo "    \"port\": $DEEPSEEK_SERVER_PORT,"
        echo "    \"health\": $(check_server_health "$DEEPSEEK_SERVER_PORT" && echo 'true' || echo 'false'),"
        echo "    \"uptime\": \"$(get_process_uptime "$(find_server_pid)")\""
        echo "  },"
        echo "  \"bridge\": {"
        echo "    \"pid\": \"$(find_bridge_pid)\","
        echo "    \"uptime\": \"$(get_process_uptime "$(find_bridge_pid)")\""
        echo "  }"
        echo "}"
        ;;
    
    --short|-s)
        # Краткий вывод (только статус)
        if [ -n "$(find_server_pid)" ] && check_server_health "$DEEPSEEK_SERVER_PORT"; then
            echo -e "${GREEN}Сервер: RUNNING${NC}"
        else
            echo -e "${RED}Сервер: STOPPED${NC}"
        fi
        
        if [ -n "$(find_bridge_pid)" ]; then
            echo -e "${GREEN}Мост: RUNNING${NC}"
        else
            echo -e "${RED}Мост: STOPPED${NC}"
        fi
        ;;
    
    help|--help|-h)
        echo ""
        echo "Использование: $0 [опции]"
        echo ""
        echo "Опции:"
        echo "  (без опций)  - Полный вывод статуса"
        echo "  -w, --watch  - Режим наблюдения (обновление каждые 5 сек)"
        echo "  -s, --short  - Краткий вывод (только статус)"
        echo "  -j, --json   - Вывод в JSON формате"
        echo "  -h, --help   - Показать эту справку"
        echo ""
        echo "Примеры:"
        echo "  $0            # Проверить статус"
        echo "  $0 --watch    # Следить за статусом"
        echo "  $0 --short    # Краткий статус"
        echo "  $0 --json     # JSON для скриптов"
        echo ""
        ;;
    
    *)
        check_all
        ;;
esac