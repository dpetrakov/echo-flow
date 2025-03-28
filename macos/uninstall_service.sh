#!/bin/bash

# Определение директорий
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PLIST_FILE="com.echoflow.filemonitor.plist"
TARGET_PLIST_PATH="$HOME/Library/LaunchAgents/$PLIST_FILE"

echo "Удаление EchoFlow Monitor Service..."

# Проверка существования plist файла
if [ ! -f "$TARGET_PLIST_PATH" ]; then
    echo "Служба не установлена."
    exit 0
fi

# Выгрузка и удаление службы
launchctl unload "$TARGET_PLIST_PATH" 2>/dev/null
rm "$TARGET_PLIST_PATH"

echo "Служба успешно удалена." 