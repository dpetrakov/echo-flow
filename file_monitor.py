#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import time
import shutil
import logging
from pathlib import Path
from dotenv import load_dotenv
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("file_monitor.log"),
        logging.StreamHandler()
    ]
)

# Загрузка переменных окружения из .env файла
load_dotenv()

# Получение переменных из .env
input_dir = os.getenv("INPUT_DIR")
monitored_dir = os.getenv("MONITORED_DIR")
min_file_size = int(os.getenv("MIN_FILE_SIZE_KB", "100")) * 1024  # Размер в КБ
check_interval = int(os.getenv("CHECK_INTERVAL", "5"))  # Интервал проверки в секундах

class WavFileHandler(FileSystemEventHandler):
    def on_created(self, event):
        if event.is_directory:
            return
        
        file_path = Path(event.src_path)
        
        # Проверяем, что это .wav файл
        if file_path.suffix.lower() == '.wav':
            # Проверяем размер файла
            try:
                # Небольшая задержка, чтобы файл успел полностью записаться
                time.sleep(1)
                
                # Получаем размер файла
                file_size = os.path.getsize(file_path)
                
                if file_size >= min_file_size:
                    # Копируем файл в INPUT_DIR
                    dest_path = os.path.join(input_dir, file_path.name)
                    logging.info(f"Копирование {file_path} (размер: {file_size/1024:.2f} КБ) в {dest_path}")
                    
                    shutil.copy2(file_path, dest_path)
                    logging.info(f"Успешно скопирован файл {file_path.name}")
                else:
                    logging.info(f"Файл {file_path} имеет недостаточный размер ({file_size/1024:.2f} КБ < {min_file_size/1024} КБ)")
            except Exception as e:
                logging.error(f"Ошибка при обработке файла {file_path}: {str(e)}")

def start_monitoring():
    logging.info(f"Запуск мониторинга директории: {monitored_dir}")
    logging.info(f"Файлы будут копироваться в: {input_dir}")
    logging.info(f"Минимальный размер файла: {min_file_size/1024} КБ")
    
    # Проверка существования директорий
    if not os.path.exists(monitored_dir):
        logging.error(f"Директория для мониторинга не существует: {monitored_dir}")
        return
        
    if not os.path.exists(input_dir):
        logging.error(f"Целевая директория не существует: {input_dir}")
        return
    
    # Создаем обработчик событий и наблюдатель
    event_handler = WavFileHandler()
    observer = Observer()
    observer.schedule(event_handler, monitored_dir, recursive=False)
    
    # Запускаем наблюдатель в отдельном потоке
    observer.start()
    
    try:
        logging.info("Мониторинг запущен. Нажмите Ctrl+C для остановки.")
        while True:
            time.sleep(check_interval)
    except KeyboardInterrupt:
        observer.stop()
    
    observer.join()
    logging.info("Мониторинг остановлен.")

if __name__ == "__main__":
    start_monitoring() 