@echo off
title DAQ System Frontend

cd /d "%~dp0frontend"

echo ========================================
echo Starting DAQ System Frontend
echo ========================================
echo.
echo IMPORTANT:
echo Do NOT close this Command Prompt while using the system.
echo Closing this window will stop the frontend app.
echo To stop the frontend safely, press CTRL + C.
echo.

if not exist ".venv" (
    echo Creating frontend virtual environment...
    python -m venv .venv
)

call ".venv\Scripts\activate.bat"

echo Installing frontend dependencies...
python -m pip install --upgrade pip
python -m pip install -r requirements.txt

echo.
echo Frontend will run at:
echo http://localhost:8501
echo.
echo Make sure the backend is also running:
echo http://127.0.0.1:8000
echo.

python -m streamlit run app.py

pause