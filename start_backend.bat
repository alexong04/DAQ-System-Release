@echo off
title DAQ System Backend

cd /d "%~dp0backend"

echo ========================================
echo Starting DAQ System Backend
echo ========================================
echo.
echo IMPORTANT:
echo Do NOT close this Command Prompt while using the system.
echo Closing this window will stop the backend server.
echo To stop the backend safely, press CTRL + C.
echo.

if not exist ".venv" (
    echo Creating backend virtual environment...
    python -m venv .venv
)

call ".venv\Scripts\activate.bat"

echo Installing backend dependencies...
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

if not exist ".env" (
    if exist ".env.example" (
        echo Creating backend .env from .env.example...
        copy ".env.example" ".env"
    )
)

if not exist "data" (
    mkdir data
)

echo.
echo Backend will run at:
echo http://127.0.0.1:8000
echo.
echo API docs:
echo http://127.0.0.1:8000/docs
echo.

python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000

pause