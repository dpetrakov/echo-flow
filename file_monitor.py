#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import time
import shutil
import logging
import subprocess
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
output_dir = os.getenv("OUTPUT_DIR")  # Директория для выходных данных (транскрипты)

def safe_copy_file(src, dst):
    """Безопасное копирование файла с использованием cp для обхода ограничений доступа"""
    try:
        # Используем команду cp для обхода ограничений доступа в macOS
        result = subprocess.run(['cp', src, dst], capture_output=True, text=True)
        
        if result.returncode != 0:
            logging.error(f"Ошибка при копировании через cp: {result.stderr}")
            return False
        return True
    except Exception as e:
        logging.error(f"Ошибка при запуске команды cp: {str(e)}")
        return False

def safe_delete_file(file_path):
    """Безопасное удаление файла"""
    try:
        if os.path.exists(file_path):
            os.remove(file_path)
            logging.info(f"Файл успешно удален: {file_path}")
            return True
        else:
            logging.warning(f"Файл не существует: {file_path}")
            return False
    except Exception as e:
        logging.error(f"Ошибка при удалении файла {file_path}: {str(e)}")
        return False

def process_pdf_file(file_path):
    """Обработка PDF файла с использованием marker_single"""
    try:
        logging.info(f"Запуск обработки PDF файла: {file_path}")
        
        # Получение API-ключа Gemini из .env файла
        gemini_api_key = os.getenv("GEMENI_API_KEY")
        
        if not gemini_api_key:
            logging.warning("API-ключ Gemini не найден в .env файле. Обработка будет выполнена без использования LLM.")
        
        # Оптимизированные параметры для marker_single
        command = [
            'marker_single',
            str(file_path),
            '--output_dir', output_dir,
            '--output_format', 'markdown',
            '--disable_tqdm',               # Отключаем прогресс-бары для фонового процесса
            '--max_concurrency', '3'        # Оптимальное количество параллельных запросов
        ]
        
        # Если ключ API Gemini доступен, добавляем параметры для использования LLM
        if gemini_api_key:
            command.extend([
                '--use_llm',                  # Включаем LLM для лучшего качества
                '--gemini_api_key', gemini_api_key,
                '--model_name', 'gemini-2.0-flash'  # Быстрая модель с хорошим качеством
            ])
        
        logging.info(f"Выполняется команда: {' '.join(command)}")
        
        result = subprocess.run(
            command,
            capture_output=True, 
            text=True
        )
        
        if result.returncode != 0:
            logging.error(f"Ошибка при обработке PDF: {result.stderr}")
            return False
        
        logging.info(f"PDF файл успешно обработан: {file_path}")
        return True
    except Exception as e:
        logging.error(f"Ошибка при запуске marker_single: {str(e)}")
        return False

def get_file_size(file_path):
    """Получение размера файла"""
    try:
        # Используем команду ls -l для проверки размера файла
        result = subprocess.run(['ls', '-l', str(file_path)], capture_output=True, text=True)
        if result.returncode != 0:
            logging.error(f"Не удалось получить информацию о файле: {result.stderr}")
            return -1
        
        # Парсим размер файла из вывода ls -l
        try:
            file_size = int(result.stdout.split()[4])
            return file_size
        except (IndexError, ValueError):
            logging.error(f"Не удалось определить размер файла: {result.stdout}")
            return -1
    except Exception as e:
        logging.error(f"Ошибка при получении размера файла {file_path}: {str(e)}")
        return -1

class FileMonitorHandler(FileSystemEventHandler):
    def __init__(self):
        super().__init__()
        # Словарь для отслеживания уже обработанных файлов
        self.processed_files = {}
    
    def on_created(self, event):
        if event.is_directory:
            return
        
        file_path = Path(event.src_path)
        
        # Проверяем, не обрабатывали ли мы уже этот файл
        if str(file_path) in self.processed_files:
            return
        
        # Небольшая задержка, чтобы файл успел полностью записаться
        time.sleep(1)
        
        file_suffix = file_path.suffix.lower()
        
        # Обработка WAV файлов
        if file_suffix == '.wav':
            self.handle_wav_file(file_path)
        # Обработка PDF файлов
        elif file_suffix == '.pdf':
            self.handle_pdf_file(file_path)
        # Обработка TXT файлов - делаем через on_modified,
        # т.к. текстовые файлы могут дописываться после создания
        elif file_suffix == '.txt' and file_path.name.endswith('_formatted.txt'):
            # Отмечаем файл как ожидающий обработки при модификации
            self.processed_files[str(file_path)] = "pending"
    
    def on_modified(self, event):
        if event.is_directory:
            return
        
        file_path = Path(event.src_path)
        file_suffix = file_path.suffix.lower()
        
        # Обрабатываем только TXT файлы с определенным форматом
        if file_suffix == '.txt' and file_path.name.endswith('_formatted.txt'):
            # Проверяем статус файла (если он был создан ранее)
            if str(file_path) in self.processed_files and self.processed_files[str(file_path)] == "pending":
                logging.info(f"Файл модифицирован и готов к обработке: {file_path}")
                
                # Ожидаем, чтобы убедиться, что файл больше не модифицируется
                time.sleep(3)
                
                # Обрабатываем файл
                self.handle_txt_file(file_path)
                
                # Отмечаем файл как обработанный
                self.processed_files[str(file_path)] = "processed"
    
    def handle_wav_file(self, file_path):
        """Обработка WAV файла"""
        try:
            file_size = get_file_size(file_path)
            if file_size < 0:
                return
            
            if file_size >= min_file_size:
                # Копируем файл в INPUT_DIR
                dest_path = os.path.join(input_dir, file_path.name)
                logging.info(f"Копирование {file_path} (размер: {file_size/1024:.2f} КБ) в {dest_path}")
                
                if safe_copy_file(str(file_path), dest_path):
                    logging.info(f"Успешно скопирован WAV файл {file_path.name}")
                    
                    # Удаляем исходный файл после успешного копирования
                    if safe_delete_file(str(file_path)):
                        logging.info(f"Исходный WAV файл удален: {file_path}")
                    else:
                        logging.error(f"Не удалось удалить исходный WAV файл: {file_path}")
                else:
                    logging.error(f"Не удалось скопировать WAV файл {file_path}")
            else:
                logging.info(f"Файл {file_path} имеет недостаточный размер ({file_size/1024:.2f} КБ < {min_file_size/1024} КБ)")
        except Exception as e:
            logging.error(f"Ошибка при обработке WAV файла {file_path}: {str(e)}")
    
    def handle_pdf_file(self, file_path):
        """Обработка PDF файла"""
        try:
            file_size = get_file_size(file_path)
            if file_size < 0:
                return
            
            # Проверка размера может быть опциональной для PDF файлов
            if file_size >= min_file_size:
                logging.info(f"Обнаружен PDF файл {file_path} (размер: {file_size/1024:.2f} КБ)")
                
                # Обработка PDF файла с помощью marker_single
                if process_pdf_file(file_path):
                    logging.info(f"PDF файл успешно обработан: {file_path.name}")
                    
                    # Удаляем исходный файл после успешной обработки
                    if safe_delete_file(str(file_path)):
                        logging.info(f"Исходный PDF файл удален: {file_path}")
                    else:
                        logging.error(f"Не удалось удалить исходный PDF файл: {file_path}")
                else:
                    logging.error(f"Не удалось обработать PDF файл: {file_path}")
            else:
                logging.info(f"PDF файл {file_path} имеет недостаточный размер ({file_size/1024:.2f} КБ < {min_file_size/1024} КБ)")
        except Exception as e:
            logging.error(f"Ошибка при обработке PDF файла {file_path}: {str(e)}")

    def handle_txt_file(self, file_path):
        """Обработка TXT файла (автоматическое удаление после создания)"""
        try:
            # Дополнительная проверка, является ли файл форматированным текстом
            if file_path.name.endswith('_formatted.txt'):
                logging.info(f"Обнаружен TXT файл {file_path}, будет удален")
                
                # Делаем небольшую задержку, чтобы дать время на завершение операций с файлом
                time.sleep(2)
                
                # Удаляем TXT файл
                if safe_delete_file(str(file_path)):
                    logging.info(f"TXT файл успешно удален: {file_path}")
                else:
                    logging.error(f"Не удалось удалить TXT файл: {file_path}")
        except Exception as e:
            logging.error(f"Ошибка при обработке TXT файла {file_path}: {str(e)}")

def start_monitoring():
    logging.info(f"Запуск мониторинга директории: {monitored_dir}")
    logging.info(f"WAV файлы будут копироваться в: {input_dir}")
    logging.info(f"PDF файлы будут обрабатываться с выводом в: {output_dir}")
    logging.info(f"Минимальный размер файла: {min_file_size/1024} КБ")
    
    # Проверка существования директорий
    if not os.path.exists(monitored_dir):
        logging.error(f"Директория для мониторинга не существует: {monitored_dir}")
        return
        
    if not os.path.exists(input_dir):
        logging.error(f"Целевая директория для WAV не существует: {input_dir}")
        return
    
    if not os.path.exists(output_dir):
        logging.error(f"Целевая директория для вывода PDF не существует: {output_dir}")
        return
    
    # Создаем обработчик событий и наблюдатель
    event_handler = FileMonitorHandler()
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