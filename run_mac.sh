#!/bin/bash

# Определение директорий
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
MACOS_DIR="$SCRIPT_DIR/macos"
VENV_DIR="$SCRIPT_DIR/.venv"

echo "EchoFlow WAV Monitor - Настройка и запуск"
echo "========================================"
echo "ВАЖНО: Для корректной работы необходим полный доступ к файлам в директории мониторинга"
echo "При появлении запросов на доступ к файлам от macOS - разрешите их"
echo "Для полного доступа к Загрузкам откройте Системные настройки > Конфиденциальность и Безопасность > Полный доступ к диску"

# Проверка наличия необходимых директорий
if [ ! -d "$MACOS_DIR" ]; then
    echo "Ошибка: Директория $MACOS_DIR не найдена."
    exit 1
fi

# Проверка прав на исполнение
chmod +x "$MACOS_DIR"/*.sh
chmod +x "$SCRIPT_DIR/file_monitor.py"

# Меню выбора действия
echo ""
echo "Выберите действие:"
echo "1. Установить и запустить службу мониторинга WAV файлов"
echo "2. Запустить службу (если уже установлена)"
echo "3. Остановить службу"
echo "4. Удалить службу"
echo "5. Проверить статус службы"
echo "6. Создать/обновить виртуальное окружение"
echo "7. Запустить мониторинг в консоли (без установки службы)"
echo "8. Выход"
echo ""

read -p "Ваш выбор [1-8]: " choice

case $choice in
    1)
        echo "Установка и запуск службы..."
        "$MACOS_DIR/install_service.sh"
        "$MACOS_DIR/start_service.sh"
        ;;
    2)
        echo "Запуск службы..."
        "$MACOS_DIR/start_service.sh"
        ;;
    3)
        echo "Остановка службы..."
        "$MACOS_DIR/stop_service.sh"
        ;;
    4)
        echo "Удаление службы..."
        "$MACOS_DIR/uninstall_service.sh"
        ;;
    5)
        echo "Проверка статуса службы..."
        "$MACOS_DIR/status_service.sh"
        ;;
    6)
        echo "Создание/обновление виртуального окружения..."
        "$MACOS_DIR/create_venv.sh"
        ;;
    7)
        echo "Запуск мониторинга в консольном режиме..."
        echo "Активация виртуального окружения..."
        
        if [ -f "$VENV_DIR/bin/activate" ]; then
            source "$VENV_DIR/bin/activate"
            echo "Виртуальное окружение активировано."
        else
            echo "Виртуальное окружение не найдено. Создание..."
            "$MACOS_DIR/create_venv.sh"
            source "$VENV_DIR/bin/activate"
        fi
        
        echo "Запуск мониторинга. Для остановки нажмите Ctrl+C"
        python3 "$SCRIPT_DIR/file_monitor.py"
        ;;
    8)
        echo "Выход"
        exit 0
        ;;
    *)
        echo "Неверный выбор"
        exit 1
        ;;
esac

echo ""
echo "Операция завершена." 