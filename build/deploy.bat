@echo off
chcp 65001 >nul
title Kirara Deployment

set "SCRIPT_DIR=%~dp0"
set "PROJECT_DIR=%SCRIPT_DIR%.."
set "MODEL_DIR=%PROJECT_DIR%\models"
set "MODEL_FILE=%SCRIPT_DIR%modelfile.txt"
set "GGUF_FILE=%MODEL_DIR%\llama-3.1-8b-instruct-reasoner-1o1_v0.3-q4_k_m.gguf"
set "TEMP_MODEL_FILE=%SCRIPT_DIR%modelfile-temp.txt"
set "REPLACE_SCRIPT=%SCRIPT_DIR%replace_from.ps1"

echo ========================================
echo    Kirara (JRVS) One-Click Deployment
echo ========================================
echo.

echo [1/5] Checking environment...
where ollama >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Ollama not found, please install Ollama first
    echo Download: https://ollama.com/download
    pause
    exit /b 1
)
echo OK: Ollama is installed

echo.
echo [2/5] Checking model file...
if not exist "%GGUF_FILE%" (
    echo ERROR: Model file not found:
    echo        %GGUF_FILE%
    echo.
    echo Please place llama-3.1-8b-instruct-reasoner-1o1_v0.3-q4_k_m.gguf in the models directory
    pause
    exit /b 1
)
echo OK: Model file found

echo.
echo [3/5] Checking Ollama service...
ollama list >nul 2>&1
if %errorlevel% neq 0 (
    echo INFO: Ollama service not running
    echo Please run 'ollama serve' in another terminal first
    echo Then re-run this script
    pause
    exit /b 1
)
echo OK: Ollama service is running

echo.
echo [4/5] Generating temporary modelfile (absolute path)...
copy "%MODEL_FILE%" "%TEMP_MODEL_FILE%" >nul
powershell -ExecutionPolicy Bypass -File "%REPLACE_SCRIPT%" "%TEMP_MODEL_FILE%" "%GGUF_FILE%"
if %errorlevel% neq 0 (
    echo ERROR: Failed to generate temporary modelfile
    del "%TEMP_MODEL_FILE%" >nul 2>&1
    pause
    exit /b 1
)
echo OK: Temporary modelfile generated

echo.
echo [5/5] Creating Kirara model...
cd /d "%SCRIPT_DIR%"
ollama create kirara -f "%TEMP_MODEL_FILE%"
if %errorlevel% neq 0 (
    echo ERROR: Failed to create model
    del "%TEMP_MODEL_FILE%" >nul 2>&1
    pause
    exit /b 1
)
del "%TEMP_MODEL_FILE%" >nul 2>&1
echo OK: Kirara model created successfully

echo.
echo ========================================
echo    Deployment Complete!
echo ========================================
echo.
echo Usage:
echo   Chat:     ollama run kirara
echo   Or select 'kirara' model in Kirara app
echo.
pause