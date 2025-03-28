#!/bin/bash

# Определение директорий
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PLIST_FILE="com.echoflow.filemonitor.plist"
TARGET_PLIST_PATH="$HOME/Library/LaunchAgents/$PLIST_FILE"

echo "Остановка EchoFlow Monitor Service..."

# Проверка существования plist файла
if [ ! -f "$TARGET_PLIST_PATH" ]; then
    echo "Ошибка: Файл $TARGET_PLIST_PATH не найден."
    echo "Служба не установлена."
    exit 1
fi

# Выгрузка службы
launchctl unload "$TARGET_PLIST_PATH"

echo "Служба успешно остановлена." 