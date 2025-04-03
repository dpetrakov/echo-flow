import os
import time
import shutil
import re
import json
from datetime import datetime, timedelta
from pathlib import Path
from dotenv import load_dotenv
import subprocess
import os.path
import calendar
import yaml
from yaml.scanner import ScannerError
import metadata_processor

def load_config():
    """Load configuration from .env file"""
    load_dotenv()
    
    vault_root = Path(os.getenv('OBSIDIAN_VAULT_ROOT'))
    if not vault_root.is_dir():
        # Если корень не указан или не существует, используем текущий каталог
        print(f"[WARNING] OBSIDIAN_VAULT_ROOT не найден или не является каталогом. Пути будут относиться к текущему каталогу.")
        vault_root = Path('.').resolve() 

    input_dir_rel = os.getenv('INPUT_DIR', 'input')
    output_dir_rel = os.getenv('OUTPUT_DIR', 'output')
    prompt_file_rel = os.getenv('PROMPT_FILE_PATH', 'prompts/autodetect.project.md')

    # Формируем абсолютные пути
    input_dir_abs = (vault_root / input_dir_rel).resolve()
    output_dir_abs = (vault_root / output_dir_rel).resolve()
    prompt_file_abs = (vault_root / prompt_file_rel).resolve()
    
    # Создаем каталоги, если их нет (для input и output)
    input_dir_abs.mkdir(parents=True, exist_ok=True)
    output_dir_abs.mkdir(parents=True, exist_ok=True)
    # Для файла промпта проверяем только существование родительского каталога
    prompt_file_abs.parent.mkdir(parents=True, exist_ok=True)
    
    return {
        'vault_root': str(vault_root),
        'input_dir': str(input_dir_abs),
        'output_dir': str(output_dir_abs),
        'check_interval': int(os.getenv('CHECK_INTERVAL', '5')),  # check interval in seconds
        'min_file_size': int(os.getenv('MIN_FILE_SIZE_KB', '100')) * 1024,  # Size in KB
        'proxy_host': os.getenv('PROXY_HOST', '45.145.242.61'),
        'proxy_port': os.getenv('PROXY_PORT', '6053'),
        'proxy_user': os.getenv('PROXY_USER', 'user213471'),
        'proxy_pass': os.getenv('PROXY_PASS', 'uv13w2'),
        'gemini_model': os.getenv('GEMINI_MODEL', 'gemini-1.5-pro'),
        'openrouter_api_key': os.getenv('OPENROUTER_API_KEY'),
        'openrouter_model': os.getenv('OPENROUTER_MODEL', 'gemini-2.5-pro-exp-03-25'), 
        'prompt_file_path': str(prompt_file_abs), 
        'metadata_check_interval': int(os.getenv('METADATA_CHECK_INTERVAL', '300')) 
    }

def ensure_directories():
    """Create required directories if they don't exist"""
    # Теперь создание каталогов происходит в load_config
    # эту функцию можно либо удалить, либо оставить пустой для обратной совместимости
    pass 
    # for dir_name in [config['input_dir'], config['output_dir']]:
    #     dir_path = Path(dir_name)
    #     if not dir_path.exists():
    #         dir_path.mkdir(parents=True)
    #         print(f"Directory created: {dir_path}")

def log_files_in_dir(directory):
    """Log files in the specified directory"""
    print(f"\n=== Files in {directory} ===")
    dir_path = Path(directory)
    if not dir_path.exists():
        print(f"Directory {directory} does not exist!")
        return
    
    found_files = False
    for file_path in dir_path.glob('*'):
        if file_path.is_file():
            found_files = True
            print(f"File: {file_path.name} ({file_path.stat().st_size} bytes)")
    
    if not found_files:
        print(f"No files found in directory {directory}.")
    print("==========================================\n")

def format_timestamp(seconds):
    """Format time in MM:SS format or HH:MM:SS if over an hour"""
    total_seconds = round(seconds)
    hours = total_seconds // 3600
    minutes = (total_seconds % 3600) // 60
    seconds = total_seconds % 60
    
    if hours > 0:
        return f"{hours}:{minutes:02d}:{seconds:02d}"
    else:
        return f"{minutes}:{seconds:02d}"

def extract_segments_to_txt(json_file, txt_file):
    """Extract segments from JSON and save to TXT"""
    print(f"Extracting segments from {json_file.name}...")
    
    if not json_file.exists():
        print(f"[ERROR] JSON file not found: {json_file}")
        return False
    
    try:
        with open(json_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        
        segments = data.get("segments", [])
        if not segments:
            print("[INFO] No segments found in JSON file.")
            return False
        
        with open(txt_file, "w", encoding="utf-8") as out:
            for seg in segments:
                start = format_timestamp(seg["start"])
                end = format_timestamp(seg["end"])
                speaker = seg.get("speaker", "SPEAKER_??")
                text = seg.get("text", "").strip()
                out.write(f"[{start} - {end}] {speaker}: {text}\n")
        
        print(f"[INFO] Segments with timestamps saved to file: {txt_file.name}")
        return True
    except Exception as e:
        print(f"[ERROR] Error processing JSON: {str(e)}")
        return False

def format_duration_for_filename(seconds):
    """Format duration in MMSS format for filename"""
    total_seconds = round(seconds)
    minutes = total_seconds // 60
    seconds = total_seconds % 60
    return f"{minutes:02d}{seconds:02d}"

def get_audio_duration(file_path):
    """Get audio duration using ffprobe"""
    try:
        cmd = ['ffprobe', '-v', 'error', '-show_entries', 'format=duration', 
               '-of', 'default=noprint_wrappers=1:nokey=1', str(file_path)]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        duration = float(result.stdout.strip())
        return duration
    except Exception as e:
        print(f"Error getting audio duration: {str(e)}")
        return 0

def generate_filename_prefix(timestamp, duration):
    """Generate filename prefix based on date, time and duration"""
    dt = datetime.strptime(timestamp, '%Y%m%d_%H%M%S')
    
    # Extract components
    month_day = dt.strftime('%m%d')  # MMDD format
    day_of_week = calendar.day_name[dt.weekday()][:2].upper()  # First two letters of day name, uppercase
    time_str = dt.strftime('%H%M%S')  # HHMMSS format
    
    # Format duration
    duration_str = format_duration_for_filename(duration)
    
    return f"{month_day}_{day_of_week}_{time_str}_{duration_str}"

def update_bat_file_with_timestamp(timestamp):
    """Update run.bat with timestamp for output filenames"""
    try:
        run_bat_path = Path("run.bat")
        if not run_bat_path.exists():
            print("[ERROR] run.bat file not found")
            return False
        
        # Read the original content
        with open(run_bat_path, "r", encoding="utf-8") as f:
            content = f.read()
        
        # Create a backup
        backup_path = run_bat_path.with_suffix(".bak")
        with open(backup_path, "w", encoding="utf-8") as f:
            f.write(content)
        
        # Set environment variable for timestamp
        os.environ["WHISPER_TIMESTAMP"] = timestamp
        
        print(f"[INFO] Set timestamp for WhisperX output files: {timestamp}")
        
        # Удаляем backup файл после использования
        if backup_path.exists():
            backup_path.unlink()
            print("[INFO] Удален временный файл run.bak")
            
        return True
    except Exception as e:
        print(f"[ERROR] Failed to update run.bat: {str(e)}")
        return False

def find_whisperx_outputs(output_dir, file_name, timestamp):
    """Find all files created by WhisperX for the given input file"""
    # List of possible intermediate file extensions
    extensions = [".json", ".txt", ".srt", ".vtt", ".tsv"]
    
    # List of patterns to search for files
    patterns = [
        f"{file_name}.json",  # Standard JSON file
        f"{file_name}_*.json",  # JSON files with any suffix
        f"{file_name}*.txt",   # TXT files
        f"{file_name}*.srt",   # SRT files 
        f"{file_name}*.vtt",   # VTT files
        f"{file_name}*.tsv",   # TSV files
        f"{file_name}_{timestamp}*.txt"  # Formatted TXT file
    ]
    
    result = set()  # Use a set instead of a list to avoid duplicates
    for pattern in patterns:
        for file_path in output_dir.glob(pattern):
            if file_path.is_file():
                # Exclude MD file and original audio file
                if not (file_path.suffix == '.md' or 
                        (file_path.suffix in ['.wav', '.mp3', '.ogg'] and timestamp in file_path.stem)):
                    result.add(file_path)
    
    return list(result)  # Return a list for compatibility

def check_no_speech(output):
    """Check if the output contains 'No active speech found in audio'"""
    return "No active speech found in audio" in output

def group_and_format_dialog(input_file, output_md, original_filename, processed_filename, timestamp, duration):
    """Group and format dialog in Markdown format"""
    print(f"Formatting dialog to Markdown...")
    
    if not input_file.exists():
        print(f"[ERROR] File not found: {input_file}")
        return False
    
    try:
        with input_file.open("r", encoding="utf-8") as f:
            lines = f.readlines()
        
        dialog = []
        current_speaker = None
        current_block = []
        
        for idx, line in enumerate(lines):
            line = line.strip()
            match = re.match(r"\[(.+?) - (.+?)\] (SPEAKER_\d{2}|Speaker \d+): (.+)", line)
            if not match:
                print(f"[WARNING] Line {idx + 1} does not match format: {line}")
                continue
            
            start, end, speaker, text = match.groups()
            if speaker != current_speaker:
                if current_block:
                    dialog.append((current_speaker, current_block))
                current_speaker = speaker
                current_block = [(start, end, text)]
            else:
                current_block.append((start, end, text))
        
        if current_block:
            dialog.append((current_speaker, current_block))
        
        speaker_map = {}
        speaker_counter = 1
        
        # Форматированная дата и время для метаданных
        formatted_date = datetime.strptime(timestamp, '%Y%m%d_%H%M%S').strftime('%Y-%m-%d %H:%M:%S')
        
        with output_md.open("w", encoding="utf-8") as out:
            # Добавляем метаданные в формате Obsidian
            out.write("---\n")
            out.write(f"created: {formatted_date}\n")
            # Используем новый формат ссылки
            out.write(f"original_filename: [[{processed_filename}|{original_filename}]]\n") 
            out.write(f"duration: {timedelta(seconds=duration)}\n")
            out.write("---\n\n")
            
            for raw_speaker, blocks in dialog:
                if raw_speaker not in speaker_map:
                    speaker_map[raw_speaker] = f"Speaker {speaker_counter}"
                    speaker_counter += 1
                name = speaker_map[raw_speaker]
                
                # Получаем время начала и окончания всего блока
                block_start = blocks[0][0]
                block_end = blocks[-1][1]
                
                out.write(f"### {name} *[{block_start} - {block_end}]*\n\n")
                for start, end, text in blocks:
                    # Убираем время из каждой строки
                    out.write(f"- {text}\n")
                out.write("\n")
        
        print(f"[DONE] Markdown file saved: {output_md.name}")
        return True
    except Exception as e:
        print(f"[ERROR] Error creating Markdown: {str(e)}")
        return False

def process_pdf_file(file_path, output_dir):
    """Process PDF file using marker_single"""
    try:
        print(f"Starting PDF file processing: {file_path}")
        
        # Get Gemini API key from .env file
        gemini_api_key = os.getenv("GEMINI_API_KEY")
        
        if not gemini_api_key:
            print("[WARNING] Gemini API key not found in .env file. Processing will be done without using LLM.")
            print("[WARNING] Качество обработки PDF может быть ниже без использования LLM.")
        else:
            print(f"[INFO] Найден API ключ Gemini. Будем использовать LLM для улучшения качества обработки PDF.")
        
        # Устанавливаем переменные окружения для прокси
        proxy_host = config['proxy_host']
        proxy_port = config['proxy_port']
        proxy_user = config['proxy_user']
        proxy_pass = config['proxy_pass']
        
        # Формируем URL прокси
        proxy_url = f"http://{proxy_user}:{proxy_pass}@{proxy_host}:{proxy_port}"
        
        # Устанавливаем переменные окружения
        os.environ['HTTPS_PROXY'] = proxy_url
        os.environ['HTTP_PROXY'] = proxy_url
        
        # Базовые параметры для marker_single
        command = [
            'marker_single',
            str(file_path),
            '--output_dir', output_dir,
            '--output_format', 'markdown',
            '--disable_tqdm',               # Отключаем прогресс-бары для фонового процесса
            '--max_concurrency', '3'        # Извлекать таблицы из PDF
        ]
        
        # Если доступен API ключ Gemini, добавляем параметры для использования LLM
        if gemini_api_key:
            command.extend([
                '--use_llm',                  # Включаем LLM для лучшего качества
                '--gemini_api_key', gemini_api_key,
                '--model_name', config['gemini_model']
            ])
        
        print(f"[EXECUTING] Команда: {' '.join(command)}")
        print(f"[INFO] Используется прокси: {proxy_url}")
        
        # Запускаем процесс с поддержкой разных кодировок
        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            encoding='utf-8',
            errors='replace'  # Заменяем нечитаемые символы на специальный символ
        )
        
        stdout, stderr = process.communicate()
        
        # Подготавливаем вывод команды для логирования и возможного использования в отчете об ошибке
        command_output = ""
        if stdout:
            command_output += "STDOUT:\n" + stdout + "\n\n"
        if stderr:
            command_output += "STDERR:\n" + stderr
        
        # Добавляем небольшую паузу перед проверкой файла
        time.sleep(1) 
            
        if process.returncode != 0:
            print(f"[ERROR] Ошибка обработки PDF: {stderr}")
            return False, command_output
        
        # Проверяем создание файла в выходном каталоге
        output_dir_path = Path(output_dir)
        base_name = file_path.stem
        
        # Ищем файл с расширением .md в правильном месте
        output_file = output_dir_path / f"{base_name}" / f"{base_name}.md"
        
        if output_file.exists():
            print(f"[SUCCESS] Создан файл маркдаун: {output_file.name}")
            return True, command_output
        else:
            print(f"[WARNING] Маркдаун файл не был создан, хотя команда завершилась успешно")
            return False, command_output
        
    except Exception as e:
        error_msg = f"[ERROR] Ошибка запуска marker_single: {str(e)}"
        print(error_msg)
        return False, error_msg

def parse_frontmatter(file_path):
    """Parse YAML frontmatter from a Markdown file."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Проверяем, есть ли frontmatter (окружен ---)
        if content.startswith('---'):
            parts = content.split('---', 2)
            if len(parts) >= 3:
                frontmatter_str = parts[1]
                main_content = parts[2]
                try:
                    metadata = yaml.safe_load(frontmatter_str)
                    # Убедимся, что metadata это словарь
                    if not isinstance(metadata, dict):
                        print(f"[WARNING] Frontmatter в файле {file_path.name} не является словарем YAML. Пропускаем.")
                        return None, main_content # Возвращаем None для метаданных
                    return metadata, main_content
                except ScannerError as e:
                    print(f"[ERROR] Ошибка парсинга YAML frontmatter в файле {file_path.name}: {e}")
                    return None, content # Возвращаем None если парсинг не удался
        
        # Если нет frontmatter или он некорректный
        print(f"[INFO] Frontmatter не найден или некорректен в файле: {file_path.name}")
        return {}, content # Возвращаем пустой словарь и весь контент

    except Exception as e:
        print(f"[ERROR] Не удалось прочитать файл {file_path.name} для парсинга frontmatter: {e}")
        return None, None # Возвращаем None, если файл не прочитался

def check_single_md_metadata(md_file: Path, config: dict):
    """Checks a single MD file for required metadata and triggers LLM if needed.
       Returns True if LLM was triggered and completed successfully,
       False if LLM was not needed, skipped, or failed with non-rate-limit error,
       'RATE_LIMIT_ERROR' if a rate limit error occurred.
    """
    if not md_file.is_file():
        print(f"[WARNING] Файл {md_file.name} не найден или не является файлом. Пропуск проверки метаданных.")
        return False # Не триггерили LLM

    print(f"Проверка метаданных файла: {md_file.name}")
    metadata, _ = parse_frontmatter(md_file)

    if metadata is None: # Ошибка чтения или парсинга файла
        print(f"[SKIPPING] Пропуск файла {md_file.name} из-за ошибки чтения/парсинга.")
        return False
    
    required_keys = {'группа', 'проект', 'событие/назначение'} 
    missing_keys = required_keys - set(metadata.keys())

    if 'проект' in missing_keys:
        print(f"[INFO] В файле {md_file.name} отсутствует 'проект'. Запуск обработки LLM...")
        try:
            # Проверяем наличие API ключа перед вызовом
            if not config.get('openrouter_api_key'):
                print("[WARNING] Ключ OPENROUTER_API_KEY не найден в .env. Вызов LLM пропущен.")
                return False
            # Проверяем наличие файла промпта перед вызовом
            prompt_file = Path(config.get('prompt_file_path', ''))
            if not prompt_file.exists():
                print(f"[WARNING] Файл промпта '{prompt_file}' не найден. Вызов LLM пропущен.")
                return False

            # Вызываем функцию из metadata_processor
            logger = metadata_processor.logger 
            llm_result = metadata_processor.process_single_file(str(md_file), config, verbose=False) 
            
            # Проверяем результат
            if llm_result == "RATE_LIMIT_ERROR":
                return "RATE_LIMIT_ERROR" # Возвращаем маркер
            elif llm_result is True: # Успешный вызов и обновление файла
                 return True
            else: # Ошибка или файл не обновлен
                 return False
                 
        except ImportError:
            print("[ERROR] Не удалось импортировать модуль metadata_processor.")
            return False
        except Exception as e:
            print(f"[ERROR] Непредвиденная ошибка при вызове обработчика LLM для файла {md_file.name}: {e}")
            import traceback
            traceback.print_exc()
            return False
    elif missing_keys:
         print(f"[WARNING] В файле {md_file.name} отсутствуют метаданные: {', '.join(missing_keys)} (кроме 'проект')")
         return False # LLM не запускался
    else:
        print(f"[OK] Все необходимые метаданные присутствуют в файле: {md_file.name}")
        return False # LLM не запускался
        
def check_and_process_metadata(output_dir, config):
    """Periodically check all .md files in output_dir for required metadata."""
    print(f"--- Запуск периодической проверки метаданных в каталоге {output_dir} ---")
    output_path = Path(output_dir)
    processed_count = 0
    llm_triggered_count = 0
    rate_limit_hit = False # Флаг для отслеживания ошибки лимита

    for md_file in output_path.glob('*.md'):
        if md_file.is_file():
            processed_count += 1
            result = check_single_md_metadata(md_file, config)
            if result == "RATE_LIMIT_ERROR":
                 print(f"[STOP] Обнаружена ошибка лимита API при обработке {md_file.name}. Остановка текущего цикла проверки метаданных.")
                 rate_limit_hit = True
                 break # Прерываем цикл
            elif result is True:
                 llm_triggered_count += 1

    status = "Завершено" if not rate_limit_hit else "Прервано из-за лимита API"
    print(f"--- Периодическая проверка метаданных завершена ({status}). Проверено файлов: {processed_count}. Запущено LLM: {llm_triggered_count} ---")

def process_file(file_path):
    """Process a single file (audio or PDF)"""
    try:
        # Get absolute path to the file
        abs_file_path = file_path.resolve()
        file_name = file_path.stem
        file_ext = file_path.suffix.lower()
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        print(f"\n>>> Starting to process file: {abs_file_path} [Session: {timestamp}]")
        
        output_dir = Path(config['output_dir'])
        md_file_to_check = None # Переменная для хранения пути к MD файлу для немедленной проверки

        # Generate new filename prefix based on file type
        if file_ext == '.pdf':
            # For PDF files, we don't need audio duration
            duration = 0
            filename_prefix = generate_filename_prefix(timestamp, duration)
            
            # Create a new filename with the new naming scheme
            new_name = f"{filename_prefix}_document{file_ext}"
            output_path = Path(config['output_dir']) / new_name
            
            # Сначала перемещаем файл в новое место с новым именем
            print(f"\n>>> Перемещение PDF файла в выходной каталог: {file_path.name} -> {output_path.name}")
            shutil.move(str(file_path), str(output_path))
            print(f"[SUCCESS] Файл успешно перемещен.")
            
            # Process PDF directly
            print(f"[PROCESSING] Обработка PDF файла: {output_path.name}")
            pdf_processed, command_output = process_pdf_file(output_path, str(Path(config['output_dir'])))
            
            # Проверяем созданные файлы маркдаун в правильном месте
            output_md_files = list(Path(config['output_dir']).glob(f"{filename_prefix}_document/{filename_prefix}_document.md"))
            
            if not pdf_processed or not output_md_files:
                # Создаем файл с информацией об ошибке
                error_message = "PDF файл был обработан без ошибок, но маркдаун файл не был создан. Возможно, PDF документ пустой или содержит только изображения без текста."
                error_md_file = create_pdf_error_markdown(file_path, output_path, timestamp, error_message, command_output)
            else:
                print(f"\n>>> [SUCCESS] PDF файл {output_path.name} успешно обработан")
                for md_file in output_md_files:
                    # Добавляем метаданные в markdown файл
                    try:
                        with md_file.open("r", encoding="utf-8") as f:
                            content = f.read()
                        
                        # Форматированная дата и время для метаданных
                        formatted_date = datetime.strptime(timestamp, '%Y%m%d_%H%M%S').strftime('%Y-%m-%d %H:%M:%S')
                        
                        # Создаем метаданные
                        metadata = (
                            "---\n"
                            f"created: {formatted_date}\n"
                            # Используем новый формат ссылки
                            f"original_filename: [[{output_path.name}|{file_path.name}]]\n" 
                            f"processed_filename: {output_path.name}\n"
                            f"processor: marker_single\n"
                            "---\n\n"
                        )
                        
                        # Записываем обновленное содержимое
                        with md_file.open("w", encoding="utf-8") as f:
                            f.write(metadata + content)
                        
                        print(f"[INFO] Добавлены метаданные в файл: {md_file.name}")
                    except Exception as e:
                        print(f"[WARNING] Не удалось добавить метаданные в файл {md_file.name}: {str(e)}")
                
                # Удаляем только временный JSON файл из правильного места
                temp_json = Path(config['output_dir']) / f"{filename_prefix}_document" / f"{filename_prefix}_document_meta.json"
                if temp_json.exists():
                    try:
                        temp_json.unlink()
                        print(f"[INFO] Удален временный файл: {temp_json.name}")
                    except Exception as e:
                        print(f"[WARNING] Не удалось удалить временный файл {temp_json.name}: {str(e)}")
                
                return True
            
            if error_md_file:
                print(f"\n>>> [WARNING] PDF файл {output_path.name} обработан, но маркдаун не создан")
                print(f"[INFO] Создан файл с информацией об ошибке: {error_md_file.name}")
            else:
                print(f"\n>>> [ERROR] Ошибка обработки PDF файла {output_path.name}")
            
            return False
        
        # Process audio files (WAV, MP3, etc.)
        duration = get_audio_duration(abs_file_path)
        print(f"Audio duration: {timedelta(seconds=duration)}")
        
        # Generate new filename prefix
        filename_prefix = generate_filename_prefix(timestamp, duration)
        
        # Update run.bat with the timestamp
        update_bat_file_with_timestamp(timestamp)
        
        # Check files in the output directory before processing
        print("Files in output directory before processing:")
        log_files_in_dir(config['output_dir'])
        
        # Run processing through run.bat
        print(f"Running script: run.bat {abs_file_path}")
        subprocess_result = subprocess.run(['run.bat', str(abs_file_path)], 
                                          check=True, 
                                          capture_output=True, 
                                          text=True)
        print(f"run.bat output:\n{subprocess_result.stdout}")
        if subprocess_result.stderr:
            print(f"run.bat errors:\n{subprocess_result.stderr}")
        
        # Check for "No active speech" message
        no_speech_detected = check_no_speech(subprocess_result.stdout)
        
        # Check files in the output directory after processing
        # print("Files in output directory after processing:")
        # log_files_in_dir(config['output_dir'])
        
        # Process JSON and create Markdown file
        output_dir = Path(config['output_dir'])
        md_file = None  # Initialize variable for MD file
        
        # Search for JSON file (various name patterns possible)
        json_file = None
        # --- ПРИОРИТЕТНЫЙ ПОИСК: Используем имя файла с меткой времени из run.bat ---
        expected_json_filename = f"{file_name}_{timestamp}.json"
        json_file_path_with_timestamp = output_dir / expected_json_filename
        if json_file_path_with_timestamp.exists():
            json_file = json_file_path_with_timestamp
            print(f"Found JSON file with expected timestamp: {json_file.name}")
        # --- КОНЕЦ ПРИОРИТЕТНОГО ПОИСКА ---
        
        # --- ФОЛБЭК ПОИСК (на случай, если имя отличается) ---
        if not json_file: # Ищем, только если основной поиск не удался
            json_candidates = list(output_dir.glob(f"{file_name}.json"))
            if json_candidates:
                json_file = json_candidates[0]
                print(f"Found JSON file (fallback 1 - no timestamp): {json_file.name}")
        
        if not json_file:
            json_candidates = list(output_dir.glob(f"{file_name}_*.json")) # Ищем с ЛЮБЫМ меткой
            if json_candidates:
                # Отсортируем по времени изменения, чтобы взять самый новый, если их несколько
                json_candidates.sort(key=lambda p: p.stat().st_mtime, reverse=True)
                json_file = json_candidates[0]
                print(f"Found JSON file (fallback 2 - wildcard timestamp): {json_file.name}")
        
        if not json_file:
            json_candidates = list(output_dir.glob(f"{file_name}.wav.json")) # Старый вариант с .wav
            if json_candidates:
                json_file = json_candidates[0]
                print(f"Found JSON file (fallback 3 - .wav suffix): {json_file.name}")
        # --- КОНЕЦ ФОЛБЭК ПОИСКА ---
        
        # Create names for output files with new naming scheme
        txt_file = output_dir / f"{filename_prefix}_formatted.txt"
        md_file = output_dir / f"{filename_prefix}_transcript.md"
        
        # Create MD file based on JSON, if found
        if json_file and not no_speech_detected:
            print("Found JSON file, starting conversion to Markdown...")
            if extract_segments_to_txt(json_file, txt_file):
                # Передаем output_path.name как processed_filename
                if group_and_format_dialog(txt_file, md_file, file_path.name, output_path.name, timestamp, duration):
                    # Удаляем formatted.txt после успешного создания markdown
                    if txt_file.exists():
                        txt_file.unlink()
                        print(f"[INFO] Удален временный файл {txt_file.name}")
                    md_file_to_check = md_file # Указываем файл для проверки
        else:
            if no_speech_detected:
                print(f"[INFO] No active speech detected in the audio file")
            else:
                print(f"[ERROR] JSON file not found in directory {output_dir}")
        
        # Create a new filename with the new naming scheme
        new_name = f"{filename_prefix}_transcript{file_ext}"
        output_path = Path(config['output_dir']) / new_name
        
        # Move the original file to the output directory
        print(f"\n>>> Moving original file to output directory: {file_path.name} -> {output_path.name}")
        shutil.move(str(file_path), str(output_path))
        print(f"File moved successfully.")
        
        # Delete intermediate files in the output directory
        print("Searching for intermediate files to delete...")
        intermediate_files = find_whisperx_outputs(output_dir, file_name, timestamp)
        
        # Check if MD file was created
        md_created = md_file_to_check and md_file_to_check.exists()
        
        if intermediate_files:
            print(f"Found {len(intermediate_files)} intermediate files:")
            for intermediate_file in intermediate_files:
                try:
                    # Check if this is a JSON file that should be preserved on error
                    is_json = intermediate_file.suffix.lower() == '.json'
                    if is_json and not md_created and not no_speech_detected:
                        print(f"Preserving JSON file for debugging: {intermediate_file.name}")
                        continue  # Skip deleting JSON file
                        
                    print(f"Deleting intermediate file: {intermediate_file.name}")
                    if intermediate_file.exists():
                        intermediate_file.unlink()
                    else:
                        print(f"File {intermediate_file.name} no longer exists.")
                except Exception as e:
                    print(f"Error deleting file {intermediate_file.name}: {str(e)}")
        else:
            print("No intermediate files found.")
        
        # Check for the final MD file
        if md_created:
            print(f"\n>>> File {file_path.name} processed successfully, Markdown created: {md_file.name}")
        else:
            # Create MD file with error information
            error_md_file = output_dir / f"{filename_prefix}_transcript_error.md"
            try:
                with error_md_file.open("w", encoding="utf-8") as f:
                    # Добавляем метаданные в формате Obsidian
                    f.write("---\n")
                    f.write(f"created: {datetime.strptime(timestamp, '%Y%m%d_%H%M%S').strftime('%Y-%m-%d %H:%M:%S')}\n")
                    # Используем новый формат ссылки
                    f.write(f"original_filename: [[{output_path.name}|{file_path.name}]]\n") 
                    f.write(f"duration: {timedelta(seconds=duration)}\n")
                    f.write(f"error: {'No speech detected' if no_speech_detected else 'Processing error'}\n")
                    f.write("---\n\n")
                    
                    if no_speech_detected:
                        f.write(f"# No speech detected in file {file_path.name}\n\n")
                        f.write(f"Processing date and time: {timestamp.replace('_', ' ')}\n\n")
                        f.write("## File Information\n\n")
                        # Используем новый формат ссылки
                        f.write(f"- Filename: [[{output_path.name}|{file_path.name}]]\n") 
                        f.write(f"- Size: {file_path.stat().st_size} bytes\n")
                        f.write(f"- Moved to: {output_path.name}\n\n")
                        f.write("The audio file was processed, but no speech was detected. This could be due to:\n\n")
                        f.write("- Silent audio file\n")
                        f.write("- Very low volume speech\n")
                        f.write("- Non-speech audio content\n")
                        f.write("- Format not compatible with speech recognition\n")
                    else:
                        f.write(f"# Error processing file {file_path.name}\n\n")
                        f.write(f"Processing date and time: {timestamp.replace('_', ' ')}\n\n")
                        
                        # Add information about JSON file if found
                        if json_file and json_file.exists():
                            f.write(f"JSON file preserved for debugging: `{json_file.name}`\n\n")
                        
                        f.write("## Processing Output\n\n")
                        f.write("```\n")
                        if 'subprocess_result' in locals() and subprocess_result:
                            f.write(subprocess_result.stdout)
                            if subprocess_result.stderr:
                                f.write("\n\n### Errors:\n")
                                f.write(subprocess_result.stderr)
                        else:
                            f.write("No processing output available.")
                        f.write("\n```\n\n")
                        
                        f.write("## Possible Error Causes\n\n")
                        f.write("- File format not supported\n")
                        f.write("- File does not contain speech\n")
                        f.write("- Error in speech recognition\n")
                        f.write("- Error in speaker identification\n")
                        
                        f.write("\n## File Information\n\n")
                        # Используем новый формат ссылки
                        f.write(f"- Filename: [[{output_path.name}|{file_path.name}]]\n") 
                        f.write(f"- Size: {file_path.stat().st_size} bytes\n")
                        f.write(f"- Moved to: {output_path.name}\n")
                    
                if no_speech_detected:
                    print(f"\n>>> File {file_path.name} contains no speech. Created information Markdown: {error_md_file.name}")
                else:
                    print(f"\n>>> File {file_path.name} processed with errors. Created error information Markdown: {error_md_file.name}")
                
                if json_file and json_file.exists() and not no_speech_detected:
                    print(f"JSON file preserved for debugging: {json_file.name}")
            except Exception as e:
                print(f"Error creating error information MD file: {str(e)}")
        
        # --- Немедленная проверка метаданных для созданного MD файла ---            
        if md_file_to_check and md_file_to_check.exists():
            print(f"\n--- Запуск немедленной проверки метаданных для {md_file_to_check.name} ---")
            # Немедленная проверка НЕ должна прерывать основной процесс,
            # даже если столкнется с лимитом. Мы просто логируем результат.
            check_result = check_single_md_metadata(md_file_to_check, config)
            if check_result == "RATE_LIMIT_ERROR":
                 print(f"[INFO] Не удалось выполнить немедленную проверку метаданных для {md_file_to_check.name} из-за лимита API.")
            print(f"--- Немедленная проверка метаданных для {md_file_to_check.name} завершена ---")
        # --- Конец немедленной проверки --- 
            
        return True
    except Exception as e:
        print(f"Error processing file {file_path}: {str(e)}")
        # Добавим traceback для лучшей диагностики
        import traceback
        traceback.print_exc()
        return False

def create_pdf_error_markdown(file_path, output_path, timestamp, error_message, command_output=None):
    """Create markdown file with error information for PDF processing"""
    try:
        # Generate error markdown filename
        error_md_file = Path(config['output_dir']) / f"{output_path.stem}_error.md"
        
        with error_md_file.open("w", encoding="utf-8") as f:
            # Добавляем метаданные в формате Obsidian
            f.write("---\n")
            f.write(f"created: {datetime.strptime(timestamp, '%Y%m%d_%H%M%S').strftime('%Y-%m-%d %H:%M:%S')}\n")
            # Используем новый формат ссылки
            f.write(f"original_filename: [[{output_path.name}|{file_path.name}]]\n") 
            f.write(f"processed_filename: {output_path.name}\n")
            f.write(f"error: PDF processing error\n")
            f.write(f"processor: marker_single\n")
            f.write("---\n\n")
            
            f.write(f"# Ошибка обработки PDF файла {output_path.name}\n\n")
            f.write(f"Дата и время обработки: {datetime.strptime(timestamp, '%Y%m%d_%H%M%S').strftime('%d.%m.%Y %H:%M:%S')}\n\n")
            
            f.write("## Детали ошибки\n\n")
            f.write(f"{error_message}\n\n")
            
            # Добавляем вывод команды, если он доступен
            if command_output:
                f.write("## Вывод команды\n\n")
                f.write("```\n")
                f.write(command_output)
                f.write("\n```\n\n")
            
            f.write("## Возможные причины ошибки\n\n")
            f.write("- PDF файл имеет неподдерживаемый формат\n")
            f.write("- PDF файл зашифрован или защищен\n")
            f.write("- Ошибка в инструменте marker_single\n")
            f.write("- Недостаточно памяти или ресурсов для обработки\n")
            f.write("- PDF файл содержит только изображения без текстового слоя\n")
            f.write("- Проблемы с ключом API для LLM\n")
            
            f.write("\n## Информация о файле\n\n")
            # Используем новый формат ссылки
            f.write(f"- Оригинальный файл: [[{output_path.name}|{file_path.name}]]\n") 
            f.write(f"- Обработанный файл: {output_path.name}\n")
            f.write(f"- Размер: {output_path.stat().st_size/1024:.2f} КБ\n")
            f.write(f"- Расположение: {output_path}\n\n")
            
            f.write("## Что делать дальше\n\n")
            f.write("1. Проверьте формат PDF файла\n")
            f.write("2. Убедитесь, что файл не защищен паролем\n")
            f.write("3. Проверьте наличие и правильность API ключа в .env файле\n")
            f.write("4. Попробуйте обработать файл вручную командой `marker_single`\n")
            f.write("5. Проверьте содержимое временного каталога для дополнительной информации\n")
        
        print(f"[INFO] Создан файл с информацией об ошибке: {error_md_file.name}")
        return error_md_file
    except Exception as e:
        print(f"[ERROR] Ошибка создания файла с информацией об ошибке PDF: {str(e)}")
        return None

def main():
    """Main service loop"""
    print(f"Service started. Monitoring directory: {config['input_dir']}")
    print(f"Files will be processed and saved to: {config['output_dir']}")
    print(f"Minimum file size: {config['min_file_size']/1024} KB")
    print(f"Supported formats: WAV, MP3, PDF")
    print(f"Metadata check interval: {config['metadata_check_interval']} seconds")
    
    # Create necessary directories at startup
    ensure_directories()
    
    # --- Первичная проверка метаданных при запуске ---    
    print("\n--- Запуск первичной проверки метаданных --- ")
    check_and_process_metadata(config['output_dir'], config)
    print("--- Первичная проверка метаданных завершена --- ")
    # --- Конец первичной проверки --- 
    
    last_metadata_check_time = time.time() 

    while True:
        try:
            # Check for new files
            input_dir = Path(config['input_dir'])
            for file_path in input_dir.glob('*'):
                if file_path.is_file():
                    # Ignore syncthing temporary files
                    if file_path.name.startswith("~syncthing~") and file_path.name.endswith(".tmp"):
                        # print(f"Ignoring syncthing temporary file: {file_path.name}") # Слишком много логов
                        continue
                    
                    # Check file size
                    file_size = file_path.stat().st_size
                    if file_size < config['min_file_size']:
                        # print(f"File {file_path.name} is too small ({file_size/1024:.2f} KB < {config['min_file_size']/1024} KB), skipping.")
                        continue
                    
                    # Check file extension
                    file_ext = file_path.suffix.lower()
                    if file_ext not in ['.wav', '.mp3', '.pdf']:
                        # print(f"Unsupported file type: {file_ext}, skipping file: {file_path.name}")
                        continue
                        
                    print(f"New file detected: {file_path.name} ({file_size/1024:.2f} KB)")
                    process_file(file_path) # Обрабатываем новый файл немедленно
            
            # Периодическая проверка метаданных
            current_time = time.time()
            if current_time - last_metadata_check_time >= config['metadata_check_interval']:
                check_and_process_metadata(config['output_dir'], config)
                last_metadata_check_time = current_time

            time.sleep(config['check_interval'])
            
        except Exception as e:
            print(f"[ERROR] Ошибка в главном цикле: {str(e)}")
            # Добавим traceback для лучшей диагностики
            import traceback
            traceback.print_exc()
            time.sleep(config['check_interval'] * 5) # Увеличим паузу при ошибке

if __name__ == "__main__":
    # Configuration loaded at startup
    config = load_config()
    
    # Print startup banner
    print("=" * 80)
    print("EchoFlow File Processor Service")
    print("Unified audio and PDF processor with Metadata Enrichment") # Обновили название
    print("=" * 80)
    
    # Проверка наличия ключа Gemini API
    gemini_api_key = os.getenv("GEMINI_API_KEY")
    if gemini_api_key:
        print(f"[CONFIG] Найден ключ Gemini API: ...{gemini_api_key[-5:]}")
        print("[CONFIG] PDF файлы будут обрабатываться с использованием LLM (Gemini)")
    else:
        print("[CONFIG] Ключ Gemini API не найден. PDF файлы будут обрабатываться без LLM.")
    
    # Проверка наличия ключа OpenRouter API
    openrouter_api_key = config.get('openrouter_api_key')
    if openrouter_api_key:
         print(f"[CONFIG] Найден ключ OpenRouter API: ...{openrouter_api_key[-5:]}")
         print(f"[CONFIG] Модель OpenRouter для метаданных: {config['openrouter_model']}")
         print(f"[CONFIG] Файл промпта для метаданных: {config['prompt_file_path']}")
         print("[CONFIG] Автоматическое определение метаданных включено.")
    else:
        print("[CONFIG] Ключ OPENROUTER_API_KEY не найден. Автоматическое определение метаданных отключено.")
        print("[CONFIG] Добавьте ключ OPENROUTER_API_KEY и PROMPT_FILE_PATH в .env для включения.")

    # Дополнительная информация о конфигурации
    print(f"[CONFIG] Каталог для мониторинга: {config['input_dir']}")
    print(f"[CONFIG] Каталог для выходных файлов: {config['output_dir']}")
    print(f"[CONFIG] Минимальный размер файла: {config['min_file_size']/1024:.1f} KB")
    print(f"[CONFIG] Интервал проверки новых файлов: {config['check_interval']} сек")
    print(f"[CONFIG] Интервал проверки метаданных: {config['metadata_check_interval']} сек")
    print("=" * 80)
    
    main() 


    # TODO: удалять аудио файлы старше недели из processed
    # TODO: добавить обработку других форматов аудио
    # TODO: Реализовать вызов metadata_processor.py из check_and_process_metadata --- DONE
