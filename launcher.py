import subprocess
import sys
import time
import webbrowser
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

backend_cmd = [
    sys.executable,
    "-m",
    "uvicorn",
    "main:app",
    "--host",
    "127.0.0.1",
    "--port",
    "8000"
]

frontend_cmd = [
    sys.executable,
    "-m",
    "streamlit",
    "run",
    str(BASE_DIR / "frontend" / "app.py"),
    "--server.address=127.0.0.1",
    "--server.port=8501",
    "--server.headless=true"
]

backend = subprocess.Popen(
    backend_cmd,
    cwd=BASE_DIR / "backend"
)

time.sleep(2)

frontend = subprocess.Popen(
    frontend_cmd,
    cwd=BASE_DIR / "frontend"
)

time.sleep(3)
webbrowser.open("http://127.0.0.1:8501")

try:
    backend.wait()
    frontend.wait()
except KeyboardInterrupt:
    backend.terminate()
    frontend.terminate()