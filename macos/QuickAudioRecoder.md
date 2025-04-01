# 🎙 Quick Audio Recorder for macOS

## 📌 Назначение
Автоматический запуск записи аудио через QuickTime Player с последующим сохранением в `.wav` и удалением оригинального `.m4a`.  
Файлы сохраняются в каталог:

```
/Users/dpetrakov/Downloads/audio_inbox
```

## ⚙️ Установка ffmpeg

Если `ffmpeg` ещё не установлен, установите его через [Homebrew](https://brew.sh):

```bash
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
brew install ffmpeg
```

Проверьте установку:

```bash
ffmpeg -version
```

## 🚀 Как создать приложение Quick Audio Recorder

1. Откройте Spotlight → найдите и запустите **Script Editor** (Редактор скриптов)
2. Вставьте следующий код:

```applescript
set audioFolder to POSIX file "/Users/dpetrakov/Downloads/audio_inbox" as alias

tell application "QuickTime Player"
	activate
	set newAudioRecording to new audio recording
	tell newAudioRecording
		start
	end tell
	display dialog "🎤 Запись началась.\nНажми OK, чтобы остановить запись и сохранить." buttons {"OK"} default button "OK"
	tell newAudioRecording to stop
	delay 0.5
end tell

-- Имя файла с меткой времени
set defaultName to "recording_" & (do shell script "date +%Y-%m-%d_%H-%M-%S")
set m4aPath to ((audioFolder as text) & defaultName & ".m4a")
set wavPath to ((audioFolder as text) & defaultName & ".wav")

tell application "QuickTime Player"
	export document 1 in file m4aPath using settings preset "Audio Only"
	delay 1
	close document 1 saving no
	quit
end tell

-- Конвертация в .wav
set m4aPosixPath to POSIX path of m4aPath
set wavPosixPath to POSIX path of wavPath

do shell script "/opt/homebrew/bin/ffmpeg -y -i " & quoted form of m4aPosixPath & " " & quoted form of wavPosixPath

-- Удаление .m4a после успешной конвертации
do shell script "rm -f " & quoted form of m4aPosixPath
```

3. Выберите **Файл → Сохранить**
   - Название: `QuickAudioRecorder`
   - Формат: **Программа (Application)**
   - Сохраните в папку `Программы`, на рабочий стол или куда удобно

## ✅ Использование

1. Двойной клик по иконке `QuickAudioRecorder`
2. QuickTime начнёт запись с микрофона (и системного звука, если настроено)
3. После завершения — нажмите OK
4. Файл `.wav` будет сохранён в папку `/Users/dpetrakov/Downloads/audio_inbox`

## 💡 Советы

- Если хотите записывать **и микрофон, и системный звук**, установите [BlackHole](https://existential.audio/blackhole/) и настройте агрегированное устройство в `Audio MIDI Setup`
- Можно привязать запуск `.app` к хоткею с помощью Raycast, Alfred или Automator
