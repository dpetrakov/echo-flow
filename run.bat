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

:: Check if output directory is provided as argument
set ARG_OUTPUT_DIR=%~2

:: Load environment variables from .env file
for /f "tokens=*" %%a in (.env) do (
    set %%a
)

:: Set output directory based on argument, then environment, then default
if not "%ARG_OUTPUT_DIR%"=="" (
    :: Use argument if provided
    set OUTPUT_DIR=%ARG_OUTPUT_DIR%
    echo [INFO] Using provided OUTPUT_DIR argument: %OUTPUT_DIR%
) else if not "%OUTPUT_DIR%"=="" (
    :: Use environment variable if argument not provided
    echo [INFO] Using OUTPUT_DIR from .env: %OUTPUT_DIR%
) else (
    :: Use default if argument and environment variable are missing
    set OUTPUT_DIR=%~dp0output
    echo [INFO] OUTPUT_DIR not set in .env or args, using default: %OUTPUT_DIR%
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

:: --- Proxy Setup ---
if defined PROXY_HOST (
    if defined PROXY_PORT (
        if defined PROXY_USER (
            if defined PROXY_PASS (
                set PROXY_URL=http://%PROXY_USER%:%PROXY_PASS%@%PROXY_HOST%:%PROXY_PORT%
            ) else (
                set PROXY_URL=http://%PROXY_HOST%:%PROXY_PORT%
            )
        ) else (
            set PROXY_URL=http://%PROXY_HOST%:%PROXY_PORT%
        )
        echo [INFO] Setting proxy for whisperx download: %PROXY_URL%
        set HTTPS_PROXY=%PROXY_URL%
        set HTTP_PROXY=%PROXY_URL%
    ) else (
        echo [WARNING] PROXY_HOST is set but PROXY_PORT is missing. Proxy not configured.
    )
) else (
    echo [INFO] No proxy settings found in .env for whisperx.
)
:: --- End Proxy Setup ---

:: Run whisperx with diarization
:: Using %OUTPUT_DIR% which is now determined by argument > env > default
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
