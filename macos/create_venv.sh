#!/bin/bash

# Определение директорий
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
VENV_DIR="$PROJECT_DIR/.venv"

echo "Создание виртуального окружения Python для EchoFlow..."

# Проверка наличия Python 3
if ! command -v python3 &> /dev/null; then
    echo "Ошибка: Python 3 не найден. Пожалуйста, установите Python 3."
    exit 1
fi

# Создание виртуального окружения, если его нет
if [ ! -d "$VENV_DIR" ]; then
    echo "Создание виртуального окружения в $VENV_DIR..."
    python3 -m venv "$VENV_DIR"
    
    if [ ! -d "$VENV_DIR" ]; then
        echo "Ошибка: Не удалось создать виртуальное окружение."
        exit 1
    fi
    
    echo "Виртуальное окружение успешно создано."
else
    echo "Виртуальное окружение уже существует в $VENV_DIR."
fi

# Активация виртуального окружения и установка зависимостей
echo "Активация виртуального окружения и установка зависимостей..."
source "$VENV_DIR/bin/activate"

# Обновление pip
echo "Обновление pip..."
pip install --upgrade pip

# Установка зависимостей
echo "Установка зависимостей из requirements.txt..."
if [ -f "$PROJECT_DIR/requirements.txt" ]; then
    pip install -r "$PROJECT_DIR/requirements.txt"
    echo "Зависимости успешно установлены."
else
    echo "Файл requirements.txt не найден в $PROJECT_DIR."
    exit 1
fi

echo ""
echo "Виртуальное окружение настроено и готово к использованию."
echo "Для ручной активации используйте команду:"
echo "source $VENV_DIR/bin/activate" 