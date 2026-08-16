#!/bin/bash
# -*- coding: utf-8 -*-

# ============================================
# ТЕСТ ПАКЕТНОЙ ОБРАБОТКИ
# ============================================

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_DIR" || exit 1

# Цвета
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

print_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
print_header() { echo -e "${BLUE}============================================${NC}"; }

print_header
echo "  🧪 ТЕСТ ПАКЕТНОЙ ОБРАБОТКИ"
print_header

# 1. Создаем тестовые файлы
print_info "Создание тестовых файлов..."

mkdir -p requests responses responses/processed responses/json

cat > requests/test1.txt << 'EOF'
Привет! Расскажи о себе.
EOF

cat > requests/test2.json << 'EOF'
{
    "question": "Что такое машинное обучение?",
    "from": "test_user@example.com"
}
EOF

cat > requests/test3.txt << 'EOF'
From: user@example.com
Session: 

Как работает нейросеть?
EOF

cat > requests/test4.json << 'EOF'
{
    "question": "Продолжим про нейросети. Что такое трансформеры?",
    "from": "user@example.com"
}
EOF

print_info "✅ Создано 4 тестовых файла в папке requests/"

# 2. Проверяем, запущен ли сервер
print_info "Проверка сервера..."
if ! curl -s -f "http://localhost:8001/healthz" > /dev/null 2>&1; then
    print_info "⚠️  Сервер не запущен. Запускаю..."
    ./scripts/04_run_server_only.sh start
    sleep 5
fi

# 3. Запускаем мост в режиме once (одноразовая обработка)
print_info "Запуск пакетной обработки..."
./scripts/05_run_bridge___client_only.sh once

# 4. Показываем результаты
echo ""
print_header
echo "  📊 РЕЗУЛЬТАТЫ ТЕСТА"
print_header

echo ""
echo -e "${BLUE}📁 Входные файлы (requests/):${NC}"
ls -la requests/ | grep -v "^total" | grep -v "^d" | sed 's/^/  /'

echo ""
echo -e "${BLUE}📁 Выходные файлы (responses/):${NC}"
ls -la responses/ | grep -v "^total" | grep -v "^d" | sed 's/^/  /'

echo ""
echo -e "${BLUE}📁 JSON ответы (responses/json/):${NC}"
ls -la responses/json/ | grep -v "^total" | grep -v "^d" | sed 's/^/  /'

echo ""
echo -e "${BLUE}📁 Обработанные файлы (responses/processed/):${NC}"
ls -la responses/processed/ | grep -v "^total" | grep -v "^d" | sed 's/^/  /'

# 5. Показываем содержимое ответов
echo ""
print_header
echo "  📄 СОДЕРЖИМОЕ ОТВЕТОВ"
print_header

for file in responses/*.md; do
    if [ -f "$file" ]; then
        echo ""
        echo -e "${YELLOW}--- $(basename "$file") ---${NC}"
        head -20 "$file"
        echo "..."
    fi
done

echo ""
print_info "✅ Тест завершен!"
print_info "  📁 Входные файлы: requests/"
print_info "  📁 Ответы: responses/"
print_info "  📁 JSON: responses/json/"
print_info "  📁 Обработанные: responses/processed/"