#!/bin/bash

sh

set -e

echo "🔍 Проверка целостности решения миграций PostgreSQL..."
echo ""

# Цвета для вывода
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

errors=0

# Функция для проверки файла
check_file() {
    local file="$1"
    local description="$2"
    
    if [ -f "$file" ]; then
        echo -e "${GREEN}✓${NC} $description"
        echo "  Файл: $file"
    else
        echo -e "${RED}✗${NC} $description"
        echo "  Файл не найден: $file"
        errors=$((errors + 1))
    fi
}

# Функция для проверки строки в файле
check_content() {
    local file="$1"
    local pattern="$2"
    local description="$3"
    
    if [ ! -f "$file" ]; then
        echo -e "${RED}✗${NC} $description (файл не найден)"
        errors=$((errors + 1))
        return
    fi
    
    if grep -q "$pattern" "$file"; then
        echo -e "${GREEN}✓${NC} $description"
    else
        echo -e "${RED}✗${NC} $description"
        echo "  Шаблон '$pattern' не найден в $file"
        errors=$((errors + 1))
    fi
}

# Функция для проверки прав доступа
check_executable() {
    local file="$1"
    local description="$2"
    
    if [ -x "$file" ]; then
        echo -e "${GREEN}✓${NC} $description"
        echo "  Права: $(stat -c '%a' "$file" 2>/dev/null || stat -f '%OLp' "$file" 2>/dev/null || echo 'readable')"
    else
        echo -e "${YELLOW}!${NC} $description (требуется chmod +x)"
        echo "  Выполните: chmod +x $file"
    fi
}

echo "📋 Проверка основных компонентов..."
echo ""

# Проверка основных файлов
check_file "backend/docker-entrypoint.sh" "Скрипт инициализации"
check_file "backend/Dockerfile.fastapi" "Dockerfile для FastAPI"
check_file "backend/alembic.ini" "Конфигурация Alembic"
check_file "backend/alembic/env.py" "Переменные окружения Alembic"
check_file "docker-compose.yml" "Docker Compose конфигурация"

echo ""
echo "🔧 Проверка конфигурации docker-entrypoint.sh..."
echo ""

check_content "backend/docker-entrypoint.sh" "DB_WAIT_TIMEOUT" "Переменная DB_WAIT_TIMEOUT"
check_content "backend/docker-entrypoint.sh" "wait_for_postgres" "Функция ожидания БД"
check_content "backend/docker-entrypoint.sh" "alembic upgrade head" "Команда миграций"
check_content "backend/docker-entrypoint.sh" "exec" "Трансляция сигналов (exec)"

echo ""
echo "🐳 Проверка Dockerfile.fastapi..."
echo ""

check_content "backend/Dockerfile.fastapi" "ENTRYPOINT.*docker-entrypoint.sh" "ENTRYPOINT для инициализации"
check_content "backend/Dockerfile.fastapi" "chmod.*x.*docker-entrypoint.sh" "Установка прав исполнения"
check_content "backend/Dockerfile.fastapi" "DB_WAIT_TIMEOUT" "Переменная окружения DB_WAIT_TIMEOUT"
check_content "backend/Dockerfile.fastapi" "DB_WAIT_INTERVAL" "Переменная окружения DB_WAIT_INTERVAL"
check_content "backend/Dockerfile.fastapi" "uvicorn.*app.main:app" "Команда запуска приложения"

echo ""
echo "🐘 Проверка конфигурации PostgreSQL в docker-compose.yml..."
echo ""

check_content "docker-compose.yml" "depends_on" "Зависимость от PostgreSQL"
check_content "docker-compose.yml" "DB_WAIT_TIMEOUT.*60" "Таймаут ожидания БД"
check_content "docker-compose.yml" "PG_DSN" "Переменная PG_DSN"

echo ""
echo "📄 Проверка документации..."
echo ""

check_file "MIGRATIONS_DOCKER_SETUP.md" "Подробная документация"
check_file "backend/DOCKER_MIGRATIONS_QUICK_START.md" "Быстрый старт"

echo ""
echo "🔑 Проверка прав исполнения..."
echo ""

if [ -f "backend/docker-entrypoint.sh" ]; then
    check_executable "backend/docker-entrypoint.sh" "Скрипт должен быть исполняемым"
fi

echo ""
echo "📊 Результаты проверки..."
echo ""

if [ $errors -eq 0 ]; then
    echo -e "${GREEN}✓ Все проверки пройдены успешно!${NC}"
    echo ""
    echo "Решение готово к использованию:"
    echo ""
    echo "Development:"
    echo "  docker-compose up -d fastapi-dev"
    echo ""
    echo "Production:"
    echo "  ENV_FILE=.env.prod docker-compose up -d fastapi"
    echo ""
    exit 0
else
    echo -e "${RED}✗ Обнаружено ошибок: $errors${NC}"
    echo ""
    echo "Требуется исправить следующие проблемы:"
    echo ""
    echo "1. Убедитесь, что backend/docker-entrypoint.sh имеет права +x:"
    echo "   chmod +x backend/docker-entrypoint.sh"
    echo ""
    echo "2. Перепроверьте конфигурацию docker-compose.yml"
    echo ""
    exit 1
fi
