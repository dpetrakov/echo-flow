@echo off
setlocal enabledelayedexpansion

:: Check if input audio file is provided
if "%~1"=="" (
    echo Please provide the path to an audio file. Example:
    echo run.bat C:\path\to\your_audio.wav
    exit /b 1
)

:: Input audio file
set AUDIO_FILE=%~1
echo [INFO] Processing audio file: %AUDIO_FILE%

:: Load environment variables from .env file
for /f "tokens=*" %%a in (.env) do (
    set %%a
)

:: Set output directory from environment or use default
if "%OUTPUT_DIR%"=="" (
    set OUTPUT_DIR=%~dp0output
    echo [INFO] OUTPUT_DIR not set in .env, using default: %OUTPUT_DIR%
) else (
    echo [INFO] OUTPUT_DIR: %OUTPUT_DIR%
)

:: Model and other parameters
set MODEL=medium
set DEVICE=cuda
set LANGUAGE=Russian

echo [INFO] Model: %MODEL%, Device: %DEVICE%, Language: %LANGUAGE%
echo [INFO] Saving results to: %OUTPUT_DIR%

:: Create output directory if it doesn't exist
if not exist "%OUTPUT_DIR%" (
    echo [INFO] Creating output directory: %OUTPUT_DIR%
    mkdir "%OUTPUT_DIR%"
)

:: Get basename of input file
for %%i in ("%AUDIO_FILE%") do set BASE_FILENAME=%%~ni

:: Get timestamp from environment or generate new one
if "%WHISPER_TIMESTAMP%"=="" (
    set TIMESTAMP=%date:~-4%%date:~3,2%%date:~0,2%_%time:~0,2%%time:~3,2%%time:~6,2%
    set TIMESTAMP=!TIMESTAMP: =0!
    echo [INFO] No timestamp provided, using generated: !TIMESTAMP!
) else (
    set TIMESTAMP=%WHISPER_TIMESTAMP%
    echo [INFO] Using provided timestamp: %TIMESTAMP%
)

:: Set output file prefix with timestamp
set OUTPUT_PREFIX=%BASE_FILENAME%_%TIMESTAMP%
echo [INFO] Output files will use prefix: %OUTPUT_PREFIX%

:: Run whisperx with diarization
python -m whisperx "%AUDIO_FILE%" ^
--model %MODEL% ^
--language %LANGUAGE% ^
--device %DEVICE% ^
--output_dir "%OUTPUT_DIR%" ^
--output_format json ^
--diarize ^
--hf_token %HF_TOKEN%

echo [INFO] Transcription completed for file: !BASE_FILENAME!
echo [DONE] Check results in: %OUTPUT_DIR%
