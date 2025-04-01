set audioFolder to POSIX file "/Users/dpetrakov/obsidian/dim/inbox" as alias

-- Запуск QuickTime и начало записи
tell application "QuickTime Player"
	activate
	set newRecording to new audio recording
	tell newRecording to start
end tell

-- Показываем напоминание в фоне
display notification "Идёт запись. Нажми ⏹ (Стоп) в QuickTime, но НЕ закрывай окно!" with title "Quick Audio Recorder"

-- Ждём, пока пользователь остановит запись (но НЕ закрывает окно)
repeat
	delay 1
	try
		tell application "QuickTime Player"
			if (count of documents) > 0 then
				set docName to name of document 1
				if docName does not contain "Запись" then
					exit repeat
				end if
			end if
		end tell
	end try
end repeat

delay 1

-- Генерация имени файла
set defaultName to "recording_" & (do shell script "date +%Y-%m-%d_%H-%M-%S")
set m4aPath to ((audioFolder as text) & defaultName & ".m4a")
set wavPath to ((audioFolder as text) & defaultName & ".wav")

-- Экспорт в m4a
with timeout of 300 seconds
	tell application "QuickTime Player"
		export document 1 in file m4aPath using settings preset "Audio Only"
		delay 2
		close document 1 saving no
		quit
	end tell
end timeout

-- Конвертация в .wav
set m4aPosixPath to POSIX path of m4aPath
set wavPosixPath to POSIX path of wavPath
do shell script "/opt/homebrew/bin/ffmpeg -y -i " & quoted form of m4aPosixPath & " " & quoted form of wavPosixPath

-- Удаление исходника
do shell script "rm -f " & quoted form of m4aPosixPath
