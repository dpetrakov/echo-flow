#!/bin/bash

# Определение директорий
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
LAUNCH_AGENTS_DIR="$HOME/Library/LaunchAgents"
PLIST_FILE="com.echoflow.filemonitor.plist"
PLIST_PATH="$SCRIPT_DIR/$PLIST_FILE"
TARGET_PLIST_PATH="$LAUNCH_AGENTS_DIR/$PLIST_FILE"
VENV_DIR="$PROJECT_DIR/.venv"

echo "Установка EchoFlow Monitor Service..."

# Проверка наличия директории LaunchAgents
if [ ! -d "$LAUNCH_AGENTS_DIR" ]; then
    echo "Создание директории $LAUNCH_AGENTS_DIR"
    mkdir -p "$LAUNCH_AGENTS_DIR"
fi

# Проверка существования plist файла
if [ ! -f "$PLIST_PATH" ]; then
    echo "Ошибка: Файл $PLIST_PATH не найден."
    exit 1
fi

# Создание виртуального окружения
echo "Проверка виртуального окружения..."
if [ ! -d "$VENV_DIR" ] || [ ! -f "$VENV_DIR/bin/activate" ]; then
    echo "Виртуальное окружение не найдено. Запуск create_venv.sh..."
    "$SCRIPT_DIR/create_venv.sh"
    
    if [ $? -ne 0 ]; then
        echo "Ошибка при создании виртуального окружения."
        exit 1
    fi
else
    echo "Виртуальное окружение существует в $VENV_DIR"
fi

# Создание копии файла plist с заменой путей
cp "$PLIST_PATH" "$TARGET_PLIST_PATH"

# Замена placeholder на полный путь к проекту
sed -i "" "s|__REPLACE_WITH_FULL_PATH__|$PROJECT_DIR|g" "$TARGET_PLIST_PATH"

# Установка прав на исполнение для скрипта
chmod +x "$PROJECT_DIR/file_monitor.py"
chmod +x "$SCRIPT_DIR/create_venv.sh"

# Абсолютные пути для .env файла
echo "Настройка абсолютных путей в .env файле..."
# Определение текущей ОС
if [[ "$OSTYPE" == "darwin"* ]]; then
    # macOS use sed -i ''
    sed -i "" "s|INPUT_DIR=.*|INPUT_DIR=$PROJECT_DIR/input|g" "$PROJECT_DIR/.env"
    sed -i "" "s|OUTPUT_DIR=.*|OUTPUT_DIR=$PROJECT_DIR/output|g" "$PROJECT_DIR/.env"
    
    # Создание директорий, если они не существуют
    mkdir -p "$PROJECT_DIR/input"
    mkdir -p "$PROJECT_DIR/output"
    
    echo "Пути в .env настроены на macOS"
fi

echo "Plist файл установлен в $TARGET_PLIST_PATH"
echo "Скрипт мониторинга: $PROJECT_DIR/file_monitor.py"
echo "Виртуальное окружение: $VENV_DIR"
echo "Установка завершена."
echo ""
echo "Для запуска службы выполните:"
echo "./start_service.sh" 