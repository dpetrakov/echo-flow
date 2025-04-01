import fitz  # PyMuPDF
from pathlib import Path
import sys
import logging
import re

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def is_table_block(block):
    """
    Определяет, является ли блок таблицей на основе его структуры
    
    Args:
        block: Блок текста из get_text("dict")
        
    Returns:
        bool: True если блок похож на таблицу, False в противном случае
    """
    if "lines" not in block:
        return False
    
    lines = block.get("lines", [])
    if len(lines) < 3:  # Минимум 3 строки для таблицы
        return False
    
    # Проверяем наличие границ (предполагаем, что таблицы имеют границы)
    # Также проверяем наличие равномерных столбцов
    
    # Собираем x-координаты начал текста (для определения столбцов)
    x_positions = []
    
    for line in lines:
        line_x_positions = []
        for span in line.get("spans", []):
            line_x_positions.append(span["origin"][0])
        if line_x_positions:
            x_positions.append(sorted(line_x_positions))
    
    if not x_positions:
        return False
    
    # Проверяем согласованность колонок между строками
    # (одинаковое количество и похожие позиции)
    col_count = [len(positions) for positions in x_positions]
    
    # Если количество колонок меньше 2 или сильно различается между строками, 
    # это не таблица
    if min(col_count) < 2 or max(col_count) - min(col_count) > 1:
        return False
    
    # Проверяем, совпадают ли позиции столбцов
    tolerance = 10  # допустимая погрешность в пикселях
    
    # Проверяем выравнивание столбцов
    consistent_alignments = 0
    total_comparisons = 0
    
    for i in range(1, len(x_positions)):
        prev_row = x_positions[i-1]
        curr_row = x_positions[i]
        
        # Вычисляем минимальное количество столбцов для сравнения
        min_cols = min(len(prev_row), len(curr_row))
        
        for j in range(min_cols):
            total_comparisons += 1
            if abs(prev_row[j] - curr_row[j]) <= tolerance:
                consistent_alignments += 1
    
    if total_comparisons == 0:
        return False
    
    alignment_ratio = consistent_alignments / total_comparisons
    return alignment_ratio >= 0.7  # 70% совпадений для определения таблицы

def extract_table_data(block):
    """
    Извлекает данные таблицы из блока
    
    Args:
        block: Блок текста из get_text("dict")
        
    Returns:
        list: Список строк таблицы, каждая строка - список ячеек
    """
    rows = []
    current_y = -1
    current_row = []
    
    # Сортируем все элементы текста по Y (строкам), затем по X (столбцам)
    all_spans = []
    
    for line in block.get("lines", []):
        for span in line.get("spans", []):
            all_spans.append({
                "text": span.get("text", "").strip(),
                "x": span["origin"][0],
                "y": span["origin"][1],
                "bbox": span["bbox"]
            })
    
    # Сортировка по y, затем по x
    all_spans.sort(key=lambda s: (s["y"], s["x"]))
    
    # Группировка по строкам (с небольшой погрешностью по Y)
    y_tolerance = 5
    
    for span in all_spans:
        if span["text"]:  # Пропускаем пустые тексты
            # Если это новая строка (Y-координата значительно отличается)
            if current_y == -1 or abs(span["y"] - current_y) > y_tolerance:
                if current_row:
                    rows.append(current_row)
                current_row = [span["text"]]
                current_y = span["y"]
            else:
                current_row.append(span["text"])
    
    # Добавляем последнюю строку
    if current_row:
        rows.append(current_row)
    
    return rows

def convert_table_to_markdown(table_rows):
    """
    Преобразует извлеченные строки таблицы в формат Markdown
    
    Args:
        table_rows (list): Список строк таблицы, каждая строка - список ячеек
        
    Returns:
        str: Таблица в формате Markdown
    """
    if not table_rows or len(table_rows) < 2:
        return ""
    
    # Найдем максимальное количество столбцов
    max_cols = max(len(row) for row in table_rows)
    
    if max_cols < 2:
        return ""  # Не таблица, если меньше 2 столбцов
    
    # Убедимся, что все строки имеют одинаковое количество столбцов
    normalized_rows = []
    for row in table_rows:
        normalized_row = row.copy()
        while len(normalized_row) < max_cols:
            normalized_row.append("")
        normalized_rows.append(normalized_row)
    
    # Строим Markdown таблицу
    md_lines = []
    
    # Заголовок таблицы (первая строка)
    md_lines.append("| " + " | ".join(normalized_rows[0]) + " |")
    
    # Разделитель
    md_lines.append("| " + " | ".join(["---" for _ in range(max_cols)]) + " |")
    
    # Данные таблицы (остальные строки)
    for row in normalized_rows[1:]:
        md_lines.append("| " + " | ".join(row) + " |")
    
    return "\n".join(md_lines)

def extract_text_and_tables(page):
    """
    Извлекает текст и таблицы со страницы PDF с сохранением их взаимного расположения
    
    Args:
        page: Объект страницы PDF
        
    Returns:
        str: Markdown-текст со встроенными таблицами
    """
    # Получаем словарь с информацией о блоках текста
    page_dict = page.get_text("dict")
    blocks = page_dict["blocks"]
    
    # Сортируем блоки по их положению сверху вниз
    blocks.sort(key=lambda b: b["bbox"][1])
    
    # Результирующий текст
    result_parts = []
    
    for block in blocks:
        # Пропускаем изображения и пустые блоки
        if block.get("type") != 0 or "lines" not in block:
            continue
        
        # Проверяем, является ли блок таблицей
        if is_table_block(block):
            table_rows = extract_table_data(block)
            if table_rows:
                md_table = convert_table_to_markdown(table_rows)
                if md_table:
                    result_parts.append("\n" + md_table + "\n")
        else:
            # Обычный текст - собираем его с сохранением структуры абзацев
            block_text = []
            
            for line in block.get("lines", []):
                line_text = " ".join(span.get("text", "") for span in line.get("spans", []))
                if line_text.strip():
                    block_text.append(line_text.strip())
            
            if block_text:
                paragraph = "\n".join(block_text)
                result_parts.append(paragraph)
    
    # Объединяем результаты с правильными промежутками между блоками
    result = ""
    for i, part in enumerate(result_parts):
        if i > 0:
            # Если предыдущий или текущий элемент - таблица, добавляем пустую строку
            if part.startswith("\n|") or result.endswith("|\n"):
                result += "\n"
            else:
                result += "\n\n"
        result += part
    
    return result

def pdf_to_markdown(pdf_path, md_path):
    """
    Конвертирует PDF файл в Markdown формат с распознаванием таблиц.
    
    Args:
        pdf_path (str или Path): Путь к входному PDF файлу
        md_path (str или Path): Путь к выходному Markdown файлу
    """
    pdf_path = Path(pdf_path)
    md_path = Path(md_path)

    if not pdf_path.exists():
        raise FileNotFoundError(f"PDF файл не найден: {pdf_path}")

    try:
        doc = fitz.open(pdf_path)
        markdown_content = []

        for page_num, page in enumerate(doc, 1):
            logger.info(f"Обработка страницы {page_num}/{len(doc)}")
            
            # Извлекаем текст и таблицы со страницы
            page_content = extract_text_and_tables(page)
            
            # Добавляем обработанный контент
            if page_content:
                markdown_content.append(page_content)
            
            # Добавляем разделитель страниц, если это не последняя страница
            if page_num < len(doc):
                markdown_content.append("\n---\n")

        # Объединяем все страницы в один документ
        result_md = "\n".join(markdown_content)
        
        # Нормализуем пробелы и переводы строк
        result_md = re.sub(r'\n{3,}', '\n\n', result_md)  # Уменьшаем количество пустых строк
        result_md = re.sub(r' +', ' ', result_md)  # Удаляем лишние пробелы
        
        # Удаляем строки с информацией о классификации и подписями
        result_md = re.sub(r'Classified as Qarmet Internal Use.*', '', result_md)
        result_md = re.sub(r'.*подписал\(а\).*\d{4}\.\d{2}\.\d{2}.*', '', result_md)
        
        # Записываем результат в файл
        md_path.write_text(result_md, encoding="utf-8")
        logger.info(f"✅ Успешно конвертирован: {pdf_path.name} -> {md_path.name}")

    except Exception as e:
        logger.error(f"❌ Ошибка при конвертации: {str(e)}")
        raise

def main():
    if len(sys.argv) != 3:
        print("Использование: python pdf_to_md.py <input.pdf> <output.md>")
        sys.exit(1)

    try:
        pdf_to_markdown(sys.argv[1], sys.argv[2])
    except Exception as e:
        logger.error(f"Ошибка: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main() 