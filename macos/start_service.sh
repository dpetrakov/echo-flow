#!/bin/bash

# Определение директорий
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
PLIST_FILE="com.echoflow.filemonitor.plist"
TARGET_PLIST_PATH="$HOME/Library/LaunchAgents/$PLIST_FILE"
VENV_DIR="$PROJECT_DIR/.venv"

echo "Запуск EchoFlow Monitor Service..."

# Проверка существования plist файла
if [ ! -f "$TARGET_PLIST_PATH" ]; then
    echo "Ошибка: Файл $TARGET_PLIST_PATH не найден."
    echo "Пожалуйста, сначала установите службу, выполнив ./install_service.sh"
    exit 1
fi

# Проверка виртуального окружения
if [ ! -d "$VENV_DIR" ] || [ ! -f "$VENV_DIR/bin/activate" ]; then
    echo "Виртуальное окружение не найдено. Запуск create_venv.sh..."
    "$SCRIPT_DIR/create_venv.sh"
    
    if [ $? -ne 0 ]; then
        echo "Ошибка при создании виртуального окружения."
        exit 1
    fi
fi

# Загрузка и запуск службы
echo "Остановка предыдущего экземпляра службы, если запущен..."
launchctl unload "$TARGET_PLIST_PATH" 2>/dev/null

echo "Запуск службы..."
launchctl load -w "$TARGET_PLIST_PATH"

echo "Служба успешно запущена."
echo "Для проверки статуса выполните:"
echo "./status_service.sh" 