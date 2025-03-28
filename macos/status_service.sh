#!/bin/bash

# Определение директорий
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
PLIST_FILE="com.echoflow.filemonitor.plist"
TARGET_PLIST_PATH="$HOME/Library/LaunchAgents/$PLIST_FILE"
LOG_FILE="/tmp/echoflow.filemonitor.out"
ERR_FILE="/tmp/echoflow.filemonitor.err"
VENV_DIR="$PROJECT_DIR/.venv"

echo "Проверка статуса EchoFlow Monitor Service..."

# Проверка существования plist файла
if [ ! -f "$TARGET_PLIST_PATH" ]; then
    echo "Статус: Служба не установлена"
    exit 1
fi

# Проверка виртуального окружения
if [ ! -d "$VENV_DIR" ] || [ ! -f "$VENV_DIR/bin/activate" ]; then
    echo "Внимание: Виртуальное окружение не найдено в $VENV_DIR"
else
    echo "Виртуальное окружение: $VENV_DIR (OK)"
fi

# Проверка статуса службы
SERVICE_STATUS=$(launchctl list | grep com.echoflow.filemonitor || echo "не запущена")

if [[ "$SERVICE_STATUS" == *"не запущена"* ]]; then
    echo "Статус: Служба установлена, но не запущена"
else
    echo "Статус: Служба активна"
    
    # Получение PID
    PID=$(echo "$SERVICE_STATUS" | awk '{print $1}')
    echo "PID процесса: $PID"
    
    # Проверка использования ресурсов
    if command -v ps &> /dev/null; then
        echo "Использование ресурсов:"
        ps -p "$PID" -o %cpu,%mem,etime
    fi
fi

# Проверка лог-файлов
echo ""
echo "Последние записи в лог-файлах:"

if [ -f "$LOG_FILE" ]; then
    echo "--- Стандартный вывод ---"
    tail -n 5 "$LOG_FILE"
else
    echo "Лог-файл еще не создан: $LOG_FILE"
fi

if [ -f "$ERR_FILE" ]; then
    echo "--- Ошибки ---"
    tail -n 5 "$ERR_FILE"
else
    echo "Файл ошибок не найден: $ERR_FILE"
fi

echo ""
echo "Конфигурация из .env файла:"
echo "Мониторинг настроен на директорию: $(grep MONITORED_DIR "$PROJECT_DIR/.env" | cut -d= -f2)"
echo "Минимальный размер файла: $(grep MIN_FILE_SIZE_KB "$PROJECT_DIR/.env" | cut -d= -f2 || echo "100") КБ"
echo "Целевая директория для копирования: $(grep INPUT_DIR "$PROJECT_DIR/.env" | cut -d= -f2)" 