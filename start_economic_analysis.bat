@echo off
setlocal

REM Find Python
where python >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo Error: Python not found. Please install Python 3.
    exit /b 1
)

REM Find the EconomicAnalysis directory
set "APP_DIR=%USERPROFILE%\EconomicAnalysis"
if not exist "%APP_DIR%" (
    echo Error: EconomicAnalysis directory not found in %USERPROFILE%
    echo Please enter the full path to your EconomicAnalysis directory:
    set /p APP_DIR=
    if not exist "%APP_DIR%" (
        echo Error: Invalid directory
        exit /b 1
    )
)

REM Run the application
cd /d "%APP_DIR%"
python run.py 