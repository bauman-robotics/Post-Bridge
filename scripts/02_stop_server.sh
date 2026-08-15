#!/bin/bash
# -*- coding: utf-8 -*-

# ============================================
# УБИЙСТВО ПРОЦЕССА НА ПОРТУ
# ============================================

# ============================================
# НАСТРОЙКИ (изменяемые параметры)
# ============================================
DEFAULT_PORT=8001  # Порт по умолчанию
# ============================================

# Цвета для вывода
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
# ФУНКЦИИ
# ============================================

show_help() {
    echo ""
    echo "Использование: $0 [порт] [опции]"
    echo ""
    echo "  [порт]          - номер порта (по умолчанию: $DEFAULT_PORT)"
    echo ""
    echo "Опции:"
    echo "  -f, --force    - принудительное убийство (kill -9)"
    echo "  -l, --list     - показать все процессы на порту"
    echo "  -h, --help     - показать эту справку"
    echo ""
    echo "Примеры:"
    echo "  $0              # Остановить процесс на порту $DEFAULT_PORT"
    echo "  $0 8080         # Остановить процесс на порту 8080"
    echo "  $0 --force      # Принудительно убить процесс на порту $DEFAULT_PORT"
    echo "  $0 8080 --force # Принудительно убить процесс на порту 8080"
    echo "  $0 --list       # Показать информацию о порту $DEFAULT_PORT"
    echo ""
}

find_process() {
    local port=$1
    local pid=""
    
    # Способ 1: через netstat
    pid=$(netstat -tulpn 2>/dev/null | grep ":$port " | grep -oP 'LISTEN\s+\K\d+' | head -1)
    
    # Способ 2: через ss
    if [ -z "$pid" ]; then
        pid=$(ss -tulpn 2>/dev/null | grep ":$port " | grep -oP 'pid=\K\d+' | head -1)
    fi
    
    # Способ 3: через lsof
    if [ -z "$pid" ]; then
        pid=$(lsof -i :$port -t 2>/dev/null | head -1)
    fi
    
    # Способ 4: через fuser
    if [ -z "$pid" ]; then
        pid=$(fuser $port/tcp 2>/dev/null | head -1)
    fi
    
    if [ -n "$pid" ]; then
        echo "$pid"
        return 0
    else
        return 1
    fi
}

get_process_info() {
    local pid=$1
    if [ -n "$pid" ]; then
        echo "PID: $pid"
        ps aux | grep -E "^[^ ]+ +$pid " | grep -v grep
    fi
}

kill_process_on_port() {
    local port=$1
    local force=$2
    
    print_header
    echo "  🎯 УБИЙСТВО ПРОЦЕССА НА ПОРТУ $port"
    print_header
    
    # Проверяем, занят ли порт
    print_info "Проверка порта $port..."
    
    local pid=$(find_process "$port")
    
    if [ -z "$pid" ]; then
        print_info "Порт $port свободен, процессов нет."
        return 0
    fi
    
    print_warn "Найден процесс на порту $port:"
    echo ""
    get_process_info "$pid"
    echo ""
    
    # Спрашиваем подтверждение
    if [ -z "$force" ]; then
        read -p "Убить процесс PID $pid? (y/N): " -n 1 -r
        echo
        if [[ ! $REPLY =~ ^[Yy]$ ]]; then
            print_info "Операция отменена."
            return 0
        fi
    fi
    
    # Убиваем процесс
    print_info "Убиваю процесс PID: $pid..."
    
    if [ "$force" == "true" ]; then
        kill -9 "$pid" 2>/dev/null
        print_info "Принудительное убийство (kill -9) выполнено."
    else
        kill "$pid" 2>/dev/null
        sleep 2
        # Проверяем, жив ли процесс
        if kill -0 "$pid" 2>/dev/null; then
            print_warn "Процесс не остановился, применяю kill -9..."
            kill -9 "$pid" 2>/dev/null
        fi
    fi
    
    # Проверяем результат
    sleep 1
    local new_pid=$(find_process "$port")
    if [ -z "$new_pid" ]; then
        print_info "✅ Процесс на порту $port успешно остановлен."
        return 0
    else
        print_error "❌ Не удалось остановить процесс. Попробуйте с опцией --force"
        return 1
    fi
}

list_process_on_port() {
    local port=$1
    
    print_header
    echo "  📊 ИНФОРМАЦИЯ О ПОРТЕ $port"
    print_header
    
    # Проверяем, занят ли порт
    if ! netstat -tuln 2>/dev/null | grep -q ":$port " && ! ss -tuln 2>/dev/null | grep -q ":$port "; then
        print_info "Порт $port свободен."
        return 0
    fi
    
    echo -e "\n🔍 Список процессов на порту $port:\n"
    
    # Показываем через netstat
    echo -e "${BLUE}--- netstat ---${NC}"
    netstat -tulpn 2>/dev/null | grep ":$port " | head -20
    echo ""
    
    # Показываем через ss
    echo -e "${BLUE}--- ss ---${NC}"
    ss -tulpn 2>/dev/null | grep ":$port " | head -20
    echo ""
    
    # Показываем через lsof
    echo -e "${BLUE}--- lsof ---${NC}"
    lsof -i :$port 2>/dev/null | head -20
    echo ""
    
    # Ищем PID и показываем информацию
    local pid=$(find_process "$port")
    if [ -n "$pid" ]; then
        echo -e "${BLUE}--- Информация о процессе (PID: $pid) ---${NC}"
        ps aux | grep -E "^[^ ]+ +$pid " | grep -v grep
        echo ""
    fi
}

# ============================================
# ОСНОВНОЙ СКРИПТ
# ============================================

# Парсинг аргументов
PORT=""
FORCE="false"
LIST="false"

# Сначала проверяем, есть ли аргументы
if [ $# -eq 0 ]; then
    # Если аргументов нет - используем порт по умолчанию
    PORT=$DEFAULT_PORT
else
    # Проверяем первый аргумент
    case $1 in
        -f|--force)
            FORCE="true"
            PORT=$DEFAULT_PORT
            shift
            ;;
        -l|--list)
            LIST="true"
            PORT=$DEFAULT_PORT
            shift
            ;;
        -h|--help)
            show_help
            exit 0
            ;;
        *)
            # Если первый аргумент - число, это порт
            if [[ $1 =~ ^[0-9]+$ ]]; then
                PORT=$1
                shift
                # Проверяем остальные аргументы
                while [[ $# -gt 0 ]]; do
                    case $1 in
                        -f|--force)
                            FORCE="true"
                            shift
                            ;;
                        -l|--list)
                            LIST="true"
                            shift
                            ;;
                        *)
                            print_error "Неизвестный аргумент: $1"
                            show_help
                            exit 1
                            ;;
                    esac
                done
            else
                print_error "Неизвестный аргумент: $1"
                show_help
                exit 1
            fi
            ;;
    esac
fi

# Проверяем, что порт указан
if [ -z "$PORT" ]; then
    print_error "Не указан порт!"
    show_help
    exit 1
fi

# Проверяем, что порт - число
if ! [[ "$PORT" =~ ^[0-9]+$ ]]; then
    print_error "Порт должен быть числом!"
    exit 1
fi

# Выполняем действие
if [ "$LIST" == "true" ]; then
    list_process_on_port "$PORT"
else
    kill_process_on_port "$PORT" "$FORCE"
fi