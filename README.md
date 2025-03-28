Отлично! Давай пошагово установим и настроим **WhisperX с GPU**, используя **оптимальную модель** для отличного качества и хорошей скорости на домашнем ПК ��⚡

---

## � **ШАГ 1. Установка Python и среды**

1. Убедись, что у тебя установлен **Python 3.10 или 3.11**
   - Проверь:  
     ```powershell
     python --version
     ```
   - Если Python не установлен — скачай с [https://www.python.org/downloads/](https://www.python.org/downloads/)

2. Рекомендуется создать виртуальное окружение:
   ```powershell
   python -m venv whisperx-env
   .\whisperx-env\Scripts\activate
   ```

---

## � **ШАГ 2. Установка PyTorch с CUDA**

Выбираем версию под **GPU NVIDIA**:

```bash
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121
```

> Заменить `cu121` на `cu118`, если у тебя старое железо (например, RTX 2060 / GTX 1660).

---

## � **ШАГ 3. Установка WhisperX**

```bash
pip install git+https://github.com/m-bain/whisperx.git
```

Если используешь виртуальное окружение — всё будет изолировано.

---

## � **ШАГ 4. Скачивание оптимальной модели**

Рекомендуемая модель: `medium` или `large-v2`

Она обеспечивает:
- Хорошее качество
- Умеренную нагрузку на GPU
- Не так прожорлива как `large` (меньше 2ГБ VRAM)

### � Скачивание произойдёт автоматически при первом запуске, но можно сделать вручную:

```bash
whisperx test.wav --model medium --language Russian --device cuda --output_format txt
```

---

## �‍♂️ **ШАГ 5. Установка speaker diarization (опционально)**

Если хочешь **разделение на голоса**, то:

1. Установи `pyannote.audio`:
   ```bash
   pip install pyannote.audio
   ```

2. Получи токен Hugging Face:
   - Перейди: [https://huggingface.co/settings/tokens](https://huggingface.co/settings/tokens)
   - Создай токен с доступом **read**

3. Выполни вход:
   ```bash
   huggingface-cli login
   ```

---

## � **ШАГ 6. Пример команды для распознавания**

```bash
whisperx C:\Users\dpetrakov\output.wav ^
--model medium ^
--language Russian ^
--device cuda ^
--output_format txt ^
--output_dir C:\Users\dpetrakov\whisperx_out ^
--diarize ^
--hf_token hf_ВАШ_ТОКЕН
```

---

## � Примечания:

| Модель         | Качество | Скорость | Потребление |
|----------------|----------|----------|--------------|
| `small`        | среднее  | � быстрая | � мало VRAM |
| `medium`       | � хорошее | � норм    | � средняя |
| `large-v2`     | �� топ   | � медленно | � до 10 ГБ VRAM |

---

Готов продолжать: могу подобрать модель под твою видеокарту, показать, как автоматизировать, или сделать `run.bat` для двойного клика. Хочешь?