#!/bin/bash
# -*- coding: utf-8 -*-

# ============================================
# ОСТАНОВКА ПОЧТОВОГО МОСТА (КЛИЕНТА)
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
PID_DIR="$PROJECT_DIR/pids"
BRIDGE_PID_FILE="$PID_DIR/bridge.pid"
LOG_DIR="$PROJECT_DIR/logs"
BRIDGE_LOG="$LOG_DIR/bridge.log"

# ============================================
# ФУНКЦИИ
# ============================================

find_bridge_pid() {
    # Ищем процесс email_bridge.py
    local pid=$(ps aux | grep -E "python.*email_bridge\.py" | grep -v grep | awk '{print $2}' | head -1)
    if [ -n "$pid" ]; then
        echo "$pid"
        return 0
    else
        return 1
    fi
}

find_bridge_pids() {
    # Ищем все процессы email_bridge.py
    ps aux | grep -E "python.*email_bridge\.py" | grep -v grep | awk '{print $2}'
}

# ============================================
# ОСНОВНАЯ ФУНКЦИЯ
# ============================================

stop_bridge() {
    print_header
    echo "  🛑 ОСТАНОВКА ПОЧТОВОГО МОСТА"
    print_header
    
    local stopped=0
    local found=0
    
    # 1. Пытаемся остановить по PID файлу
    if [ -f "$BRIDGE_PID_FILE" ]; then
        local pid=$(cat "$BRIDGE_PID_FILE")
        if kill -0 "$pid" 2>/dev/null; then
            found=1
            print_info "Остановка моста (PID: $pid)..."
            kill "$pid" 2>/dev/null
            sleep 2
            
            # Проверяем, остановился ли
            if kill -0 "$pid" 2>/dev/null; then
                print_warn "Процесс не остановился, применяю kill -9..."
                kill -9 "$pid" 2>/dev/null
                sleep 1
            fi
            
            # Проверяем результат
            if ! kill -0 "$pid" 2>/dev/null; then
                print_info "✅ Мост остановлен (PID: $pid)"
                stopped=1
            else
                print_error "❌ Не удалось остановить процесс (PID: $pid)"
            fi
            rm -f "$BRIDGE_PID_FILE"
        else
            print_warn "Процесс из PID файла не запущен (PID: $pid)"
            rm -f "$BRIDGE_PID_FILE"
        fi
    fi
    
    # 2. Ищем другие процессы моста
    local other_pids=$(find_bridge_pids)
    if [ -n "$other_pids" ]; then
        for pid in $other_pids; do
            # Пропускаем если уже остановили
            if [ "$pid" == "$(cat "$BRIDGE_PID_FILE" 2>/dev/null)" ]; then
                continue
            fi
            
            found=1
            print_info "Найден дополнительный процесс (PID: $pid), останавливаю..."
            kill "$pid" 2>/dev/null
            sleep 2
            
            if kill -0 "$pid" 2>/dev/null; then
                print_warn "Процесс не остановился, применяю kill -9..."
                kill -9 "$pid" 2>/dev/null
            fi
            
            if ! kill -0 "$pid" 2>/dev/null; then
                print_info "✅ Процесс остановлен (PID: $pid)"
                stopped=1
            fi
        done
    fi
    
    # 3. Итог
    echo ""
    if [ "$found" -eq 0 ]; then
        print_info "Мост не был запущен"
    elif [ "$stopped" -eq 1 ]; then
        print_info "✅ Мост успешно остановлен"
    else
        print_warn "⚠️  Не все процессы удалось остановить"
        print_info "   Проверьте вручную: ps aux | grep email_bridge"
    fi
    
    # 4. Показываем последние строки лога
    if [ -f "$BRIDGE_LOG" ]; then
        echo ""
        print_info "Последние строки лога:"
        tail -3 "$BRIDGE_LOG" 2>/dev/null | sed 's/^/  /'
    fi
    
    print_header
}

# ============================================
# ЗАПУСК
# ============================================

case "$1" in
    -f|--force)
        # Принудительная остановка (без подтверждения)
        print_header
        echo "  ⚡ ПРИНУДИТЕЛЬНАЯ ОСТАНОВКА МОСТА"
        print_header
        
        local pids=$(find_bridge_pids)
        if [ -n "$pids" ]; then
            for pid in $pids; do
                print_info "Убиваю процесс (PID: $pid)..."
                kill -9 "$pid" 2>/dev/null
            done
            rm -f "$BRIDGE_PID_FILE"
            print_info "✅ Все процессы моста остановлены"
        else
            print_info "Мост не запущен"
        fi
        ;;
    
    -k|--kill)
        # Убить все процессы моста
        print_header
        echo "  💀 УБИЙСТВО ВСЕХ ПРОЦЕССОВ МОСТА"
        print_header
        
        local pids=$(find_bridge_pids)
        if [ -n "$pids" ]; then
            for pid in $pids; do
                print_info "Убиваю процесс (PID: $pid)..."
                kill -9 "$pid" 2>/dev/null
            done
            rm -f "$BRIDGE_PID_FILE"
            print_info "✅ Все процессы моста убиты"
        else
            print_info "Мост не запущен"
        fi
        ;;
    
    -s|--status)
        # Проверить статус
        local pid=$(find_bridge_pid)
        if [ -n "$pid" ]; then
            echo -e "${GREEN}✅ Мост запущен (PID: $pid)${NC}"
            echo "   Время работы: $(ps -p "$pid" -o etime= 2>/dev/null | xargs)"
            echo "   CPU: $(ps -p "$pid" -o %cpu= 2>/dev/null | xargs)%"
            echo "   RAM: $(ps -p "$pid" -o %mem= 2>/dev/null | xargs)%"
        else
            echo -e "${RED}❌ Мост не запущен${NC}"
        fi
        ;;
    
    -h|--help)
        echo ""
        echo "Использование: $0 [опции]"
        echo ""
        echo "Опции:"
        echo "  (без опций)   - Остановить мост (с подтверждением)"
        echo "  -f, --force   - Принудительная остановка (без подтверждения)"
        echo "  -k, --kill    - Убить все процессы моста"
        echo "  -s, --status  - Проверить статус моста"
        echo "  -h, --help    - Показать эту справку"
        echo ""
        echo "Примеры:"
        echo "  $0            # Остановить мост"
        echo "  $0 --force    # Принудительно остановить"
        echo "  $0 --kill     # Убить все процессы"
        echo "  $0 --status   # Проверить статус"
        echo ""
        ;;
    
    *)
        # Обычная остановка
        stop_bridge
        ;;
esac