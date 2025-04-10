import os
import json
import argparse
import logging
from pathlib import Path
from dotenv import load_dotenv
import yaml
from yaml.scanner import ScannerError
from openai import OpenAI, OpenAIError, RateLimitError

# --- Logging Setup ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# --- Configuration Loading ---
def load_config():
    """Load configuration from .env file for LLM processing."""
    load_dotenv()
    
    vault_root_str = os.getenv('OBSIDIAN_VAULT_ROOT')
    if not vault_root_str or not Path(vault_root_str).is_dir():
        print(f"[WARNING] OBSIDIAN_VAULT_ROOT не найден или не является каталогом. Пути будут относиться к текущему каталогу.")
        vault_root = Path('.').resolve()
    else:
        vault_root = Path(vault_root_str).resolve()

    output_dir_rel = os.getenv('OUTPUT_DIR', 'output')
    prompt_file_rel = os.getenv('PROMPT_FILE_PATH', 'prompts/autodetect.project.md')

    # Формируем абсолютные пути
    output_dir_abs = (vault_root / output_dir_rel).resolve()
    # Путь к промпту может быть абсолютным или относительным от корня хранилища
    prompt_file_path = Path(prompt_file_rel)
    if prompt_file_path.is_absolute():
         prompt_file_abs = prompt_file_path.resolve()
    else:
         prompt_file_abs = (vault_root / prompt_file_rel).resolve()

    # Убедимся, что директория output существует, если нет - создадим
    output_dir_abs.mkdir(parents=True, exist_ok=True)
    
    # Убедимся, что директория для промптов существует
    prompt_file_abs.parent.mkdir(parents=True, exist_ok=True) 

    return {
        'vault_root': str(vault_root), # Добавляем корень хранилища в конфиг
        'output_dir': str(output_dir_abs),
        'openrouter_api_key': os.getenv('OPENROUTER_API_KEY'),
        'openrouter_model': os.getenv('OPENROUTER_MODEL', 'mistralai/mistral-7b-instruct'),
        'prompt_file_path': str(prompt_file_abs),
        'proxy_host': os.getenv('PROXY_HOST'),
        'proxy_port': os.getenv('PROXY_PORT'),
        'proxy_user': os.getenv('PROXY_USER'),
        'proxy_pass': os.getenv('PROXY_PASS'),
    }

# --- Frontmatter Parsing ---
def parse_frontmatter(file_path: Path):
    """Parse YAML frontmatter from a Markdown file. Returns (metadata, content)."""
    try:
        content = file_path.read_text(encoding='utf-8')
        if content.startswith('---'):
            parts = content.split('---', 2)
            if len(parts) >= 3:
                frontmatter_str = parts[1]
                main_content = parts[2].strip()
                try:
                    metadata = yaml.safe_load(frontmatter_str)
                    if not isinstance(metadata, dict):
                        logger.warning(f"Frontmatter в файле {file_path.name} не является словарем YAML.")
                        return {}, main_content # Возвращаем пустой словарь, но контент оставляем
                    return metadata, main_content
                except ScannerError as e:
                    logger.error(f"Ошибка парсинга YAML frontmatter в файле {file_path.name}: {e}")
                    return {}, content # Возвращаем пустой словарь и весь контент при ошибке парсинга
        # Если нет frontmatter или он некорректный
        logger.info(f"Frontmatter не найден или некорректен в файле: {file_path.name}")
        return {}, content # Возвращаем пустой словарь и весь контент

    except Exception as e:
        logger.error(f"Не удалось прочитать файл {file_path.name} для парсинга frontmatter: {e}")
        return None, None # Возвращаем None, если файл не прочитался

# --- Prompt and Context Reading (Обновлено) ---
def read_prompt_and_context(prompt_file_path: Path, vault_root: Path):
    """Reads the main prompt file and context files specified in its frontmatter (relative to vault_root)."""
    prompt_metadata, system_prompt_content = parse_frontmatter(prompt_file_path)

    if system_prompt_content is None: # Ошибка чтения файла промпта
        return None, None

    context_content = ""
    loaded_context_files = []
    failed_context_files = []

    if prompt_metadata and 'context_files' in prompt_metadata and isinstance(prompt_metadata['context_files'], list):
        logger.info(f"Найдены файлы контекста в {prompt_file_path.name}: {prompt_metadata['context_files']}")
        # base_dir = prompt_file_path.parent # Больше не используется
        for context_file_rel_path_str in prompt_metadata['context_files']:
            # Путь считается относительным к vault_root.
            # Удаляем возможный начальный слэш, так как Path его не любит при объединении
            context_file_rel_path = Path(context_file_rel_path_str.lstrip('/'))
            context_file_abs_path = (vault_root / context_file_rel_path).resolve()
            
            if context_file_abs_path.exists() and context_file_abs_path.is_file():
                try:
                    logger.debug(f"Чтение файла контекста: {context_file_abs_path}")
                    context_content += f"--- Содержимое файла {context_file_rel_path_str} ---\n"
                    context_content += context_file_abs_path.read_text(encoding='utf-8')
                    context_content += "\n---\n\n"
                    loaded_context_files.append(context_file_rel_path_str)
                except Exception as e:
                    logger.warning(f"Не удалось прочитать файл контекста {context_file_abs_path}: {e}")
                    failed_context_files.append(f"{context_file_rel_path_str} (ошибка чтения)")
            else:
                logger.warning(f"Файл контекста не найден или не является файлом: {context_file_abs_path}")
                failed_context_files.append(f"{context_file_rel_path_str} (не найден)")
    else:
        if prompt_metadata and 'context_files' in prompt_metadata:
             logger.warning("Ключ 'context_files' в файле промпта не является списком.")
        else:
             logger.info("Спецификация context_files не найдена в файле промпта.")

    # Логирование результатов загрузки контекста
    if loaded_context_files:
        logger.info(f"Успешно загружены файлы контекста: {', '.join(loaded_context_files)}")
    if failed_context_files:
        logger.warning(f"Не удалось загрузить файлы контекста: {', '.join(failed_context_files)}")

    return system_prompt_content.strip(), context_content.strip()

# --- OpenRouter API Call (Обновлено для обработки 429) ---
def call_openrouter(api_key: str, model: str, system_prompt: str, context: str, file_content: str, config: dict):
    """Calls the OpenRouter API, handles rate limits."""
    if not api_key:
        logger.error("Ключ OpenRouter API не предоставлен.")
        return None

    logger.info(f"Вызов OpenRouter API с моделью: {model}")

    # Собираем полный промпт для пользователя (исправлено)
    context_block = f"Дополнительный контекст:\n{context}\n\n" if context else ""

    user_prompt = f"""{context_block}Проанализируй содержимое следующего файла и верни ТОЛЬКО JSON объект с метаданными ('группа', 'проект', 'клиент', 'событие/назначение'):

--- Начало содержимого файла ---
{file_content}
--- Конец содержимого файла ---"""

    try:
        # Настройка клиента OpenAI для OpenRouter
        client_args = {
            "base_url": "https://openrouter.ai/api/v1",
            "api_key": api_key,
            "default_headers": { # Необязательные заголовки для OpenRouter
                 "HTTP-Referer": "http://localhost", # Замените на ваш URL, если есть
                 "X-Title": "EchoFlow Metadata Processor",
             }
        }

        # Добавляем прокси если он настроен
        if config.get('proxy_host') and config.get('proxy_port'):
             proxy_url = f"http://{config['proxy_user']}:{config['proxy_pass']}@{config['proxy_host']}:{config['proxy_port']}" if config.get('proxy_user') else f"http://{config['proxy_host']}:{config['proxy_port']}"
             logger.info(f"Попытка использовать системные настройки прокси (если установлены переменные окружения HTTPS_PROXY/HTTP_PROXY)")


        client = OpenAI(**client_args)

        # Уменьшаем логирование промптов
        logger.debug(f"System Prompt length: {len(system_prompt)}")
        logger.debug(f"User Prompt length: {len(user_prompt)}")
        # Убираем вывод полного текста:
        # logger.debug(f"""System Prompt:
        # {system_prompt}""")
        # logger.debug(f"""User Prompt (first 500 chars):
        # {user_prompt[:500]}...""")

        logger.info("Отправка запроса к LLM API...") # Лог перед вызовом
        completion = None # Инициализируем completion
        try:
            completion = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                response_format={"type": "json_object"}, # Просим модель вернуть JSON
                timeout=120.0 # Добавляем таймаут в секундах (120 секунд = 2 минуты)
            )
            logger.info("Ответ от LLM API получен.") # Лог после успешного вызова
        except RateLimitError as e: # Ловим специфичную ошибку RateLimitError
            logger.warning(f"Превышен лимит запросов (429) для модели {model}. Ответ API: {e}")
            return "RATE_LIMIT_ERROR" # Возвращаем маркер
        except OpenAIError as e: 
            # Проверяем, содержит ли ошибка информацию о коде 429 (на случай, если не RateLimitError)
            if hasattr(e, 'status_code') and e.status_code == 429:
                 logger.warning(f"Превышен лимит запросов (429) для модели {model}. Ответ API: {e}")
                 return "RATE_LIMIT_ERROR"
            # Другие ошибки OpenAI
            logger.error(f"Ошибка OpenAI API во время запроса: {e}")
            return None
        except Exception as e: # Ловим другие ошибки (включая таймаут)
            logger.error(f"Ошибка во время вызова LLM API (возможно, таймаут): {e}")
            return None

        if completion is None: # Если запрос не удался
             logger.error("Не удалось получить ответ от LLM API (запрос завершился с ошибкой).")
             return None

        # --- Проверка наличия ошибки 429 в ТЕЛЕ ответа (как было в логах) --- 
        if hasattr(completion, 'error') and completion.error:
            error_info = completion.error
            # Проверяем наличие кода и его значение
            if isinstance(error_info, dict) and error_info.get('code') == 429:
                 logger.warning(f"Превышен лимит запросов (429) для модели {model} (обнаружено в теле ответа). Ответ API: {error_info}")
                 return "RATE_LIMIT_ERROR"
            else:
                # Логируем другую ошибку из тела ответа
                logger.error(f"API вернуло ошибку в теле ответа: {error_info}")
                return None 
        # --- Конец проверки ошибки в теле --- 

        # --- Проверки структуры успешного ответа (реструктурировано) --- 
        response_content = None # Инициализируем
        if completion.choices:
            choice = completion.choices[0]
            if choice and choice.message and choice.message.content:
                # Все проверки прошли, извлекаем контент
                response_content = choice.message.content
            else:
                # Логируем конкретную причину сбоя
                if choice is None:
                    logger.error(f"Первый элемент 'choices' в ответе LLM API равен None. Ответ: {completion}")
                elif choice.message is None:
                    logger.error(f"Поле 'message' в ответе LLM API равно None. Ответ: {completion}")
                elif choice.message.content is None:
                    logger.error(f"Поле 'content' в 'message' ответа LLM API равно None. Ответ: {completion}")
                return None # Возвращаем None, если какая-либо часть отсутствует
        else:
             logger.error(f"Ответ от LLM API не содержит 'choices'. Ответ: {completion}")
             return None

        # Если мы здесь, response_content должен быть не None (или функция вернула None выше)
        if response_content is None:
             logger.error("Не удалось извлечь content из ответа LLM по неизвестной причине.")
             return None
        # --- Конец проверок --- 
            
        # response_content = choice.message.content # Старая строка, теперь присвоение выше
        logger.debug(f"Ответ от LLM (сырой): {response_content}")

        # Пытаемся распарсить JSON из ответа
        try:
            metadata_json = json.loads(response_content)
            if isinstance(metadata_json, dict):
                logger.info(f"Успешно получен и распарсен JSON от LLM: {metadata_json}")
                return metadata_json
            else:
                logger.error(f"Ответ LLM не является JSON объектом: {response_content}")
                return None
        except json.JSONDecodeError as e:
            # Используем многострочный f-string для логгирования ошибки
            logger.error(f"""Не удалось распарсить JSON из ответа LLM: {e}
Ответ: {response_content}""")
            return None

    except OpenAIError as e:
        logger.error(f"Ошибка при вызове OpenRouter API: {e}")
        return None
    except Exception as e:
        logger.error(f"Непредвиденная ошибка при вызове API: {e}")
        return None

# --- Markdown Update ---
def update_markdown_frontmatter(file_path: Path, new_metadata: dict, original_content: str):
    """Updates the Markdown file with new frontmatter, merging with existing."""
    try:
        existing_metadata, _ = parse_frontmatter(file_path) # Перечитываем на всякий случай
        if existing_metadata is None:
            existing_metadata = {} # Если парсинг не удался, начинаем с пустого

        # Объединяем метаданные: новые данные от LLM перезаписывают существующие, если ключи совпадают
        # Но лучше добавлять только недостающие или явно указанные для обновления
        # В нашем случае, LLM возвращает полный набор, так что просто обновим существующие
        # или добавим новые. Не будем удалять то, чего нет в ответе LLM.
        merged_metadata = existing_metadata.copy()
        merged_metadata.update(new_metadata)

        # Преобразуем обратно в YAML
        updated_frontmatter_str = yaml.dump(merged_metadata, allow_unicode=True, default_flow_style=False)

        # Собираем новый контент файла (исправлено)
        new_content = f"""---
{updated_frontmatter_str}---

{original_content}"""

        # Записываем обновленный файл
        file_path.write_text(new_content, encoding='utf-8')
        logger.info(f"Файл {file_path.name} успешно обновлен новыми метаданными.")
        return True

    except Exception as e:
        logger.error(f"Не удалось обновить frontmatter в файле {file_path.name}: {e}")
        return False

# --- Main Processing Function (Обновлено) ---
def process_single_file(file_path_str: str, config: dict, verbose: bool = False):
    """Processes a single Markdown file to enrich its metadata using LLM."""
    if verbose:
        logger.setLevel(logging.DEBUG)
        logger.debug("Включен режим подробного логирования.")

    file_path = Path(file_path_str)
    if not file_path.exists() or not file_path.is_file():
        logger.error(f"Файл не найден или не является файлом: {file_path_str}")
        return False

    if file_path.suffix.lower() != '.md':
        logger.error(f"Файл не является Markdown файлом (.md): {file_path_str}")
        return False

    logger.info(f"Начало обработки файла: {file_path.name}")

    # 1. Загрузка промпта и контекста
    prompt_file = Path(config['prompt_file_path'])
    vault_root = Path(config['vault_root'])
    if not prompt_file.exists():
        logger.error(f"Файл промпта не найден: {prompt_file}")
        return False

    # Передаем vault_root в функцию чтения промпта
    system_prompt, context_str = read_prompt_and_context(prompt_file, vault_root)
    if system_prompt is None:
        logger.error(f"Не удалось прочитать промпт или контекст из {prompt_file}")
        return False
    logger.debug(f"Загружен системный промпт ({len(system_prompt)} симв.) и контекст ({len(context_str)} симв.).")

    # 2. Чтение содержимого целевого файла (без frontmatter)
    _, file_content = parse_frontmatter(file_path)
    if file_content is None:
        logger.error(f"Не удалось прочитать содержимое файла: {file_path.name}")
        return False
    logger.debug(f"Загружено содержимое файла {file_path.name} ({len(file_content)} симв.).")


    # 3. Вызов LLM
    llm_result = call_openrouter(
        api_key=config['openrouter_api_key'],
        model=config['openrouter_model'],
        system_prompt=system_prompt,
        context=context_str,
        file_content=file_content,
        config=config
    )

    # Обрабатываем результат вызова LLM
    if llm_result == "RATE_LIMIT_ERROR":
        logger.info(f"Обработка файла {file_path.name} прервана из-за лимита API.")
        return "RATE_LIMIT_ERROR" # Передаем маркер дальше
        
    if not isinstance(llm_result, dict): # Если это None или другая ошибка
        logger.error(f"Не удалось получить валидные метаданные от LLM для файла {file_path.name}. Результат: {llm_result}")
        return False # Считаем это ошибкой обработки файла

    # 4. Обновление файла (только если llm_result - это dict)
    success = update_markdown_frontmatter(file_path, llm_result, file_content)

    if success:
        logger.info(f"Успешно завершена обработка файла: {file_path.name}")
        return True
    else:
        logger.error(f"Ошибка при обновлении файла: {file_path.name}")
        return False

# --- Command Line Interface ---
if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Обогащение метаданных Markdown файлов с помощью LLM через OpenRouter.")
    parser.add_argument("--file", required=True, help="Путь к Markdown файлу для обработки.")
    parser.add_argument("--verbose", action="store_true", help="Включить подробное логирование.")

    args = parser.parse_args()

    config = load_config()

    if not config.get('openrouter_api_key'):
        logger.error("Ключ OPENROUTER_API_KEY не найден в .env файле. Завершение работы.")
        exit(1)
    
    if not Path(config.get('prompt_file_path', '')).exists():
        logger.error(f"Файл промпта '{config.get('prompt_file_path')}' не найден. Завершение работы.")
        exit(1)

    process_single_file(args.file, config, args.verbose) 