# Setup Guide

This guide explains how to install and run the Pump Data Acquisition System for release use.

The system has two parts:

1. **Backend** — FastAPI server that receives Arduino/HC-05 data, computes engineering values, records sessions, and exports CSV files.
2. **Frontend** — Streamlit dashboard that displays live readings, loads saved sessions, compares sessions, and provides user controls.

---

## 1. Requirements

### Required software

Install the following before running the system:

- Python 3.10 or newer
- Git
- A modern browser such as Chrome, Edge, or Firefox
- Arduino IDE, only if uploading or modifying the Arduino sketch

### Required hardware for real data

- Arduino Mega 2560
- HC-05 Bluetooth module
- Four pressure sensors
- One YF-B10-S flow sensor
- Computer with Bluetooth support

### Optional testing mode

The backend includes a `SIMULATOR` mode. Use this when the Arduino or HC-05 is not connected yet.

---

## 2. Recommended folder structure

Place the backend and frontend folders inside one release folder:

```text
DAQ-System-Release/
├── backend/
├── frontend/
├── README.md
├── setup_guide.md
├── user_manual.md
├── start_backend.bat
└── start_frontend.bat
```

If the backend and frontend are separate GitHub repositories, clone both repositories into the same release folder:

```bash
git clone <backend-repository-url> backend
git clone <frontend-repository-url> frontend
```

Replace the URLs with the actual GitHub repository links.

---

## 3. Backend setup

Open a terminal in the release folder, then run:

```bash
cd backend
python -m venv venv
```

### Windows PowerShell

```powershell
venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

### Windows Command Prompt

```bat
venv\Scripts\activate.bat
pip install -r requirements.txt
copy .env.example .env
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

### macOS/Linux

```bash
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

The backend should run at:

```text
http://127.0.0.1:8000
```

Open this page to verify the API documentation:

```text
http://127.0.0.1:8000/docs
```

---

## 4. Frontend setup

Open a second terminal in the release folder, then run:

```bash
cd frontend
python -m venv venv
```

### Windows PowerShell

```powershell
venv\Scripts\activate
pip install -r requirements.txt
python -m streamlit run app.py
```

### Windows Command Prompt

```bat
venv\Scripts\activate.bat
pip install -r requirements.txt
python -m streamlit run app.py
```

### macOS/Linux

```bash
source venv/bin/activate
pip install -r requirements.txt
python -m streamlit run app.py
```

The dashboard should open automatically in the browser. If it does not, copy the local URL shown in the terminal and paste it into the browser.

---

## 5. Optional Windows launcher scripts

Place these files in the release repository root.

### `start_backend.bat`

```bat
@echo off
cd /d "%~dp0backend"
if not exist venv (
    python -m venv venv
)
call venv\Scripts\activate.bat
pip install -r requirements.txt
if not exist .env (
    copy .env.example .env
)
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
pause
```

### `start_frontend.bat`

```bat
@echo off
cd /d "%~dp0frontend"
if not exist venv (
    python -m venv venv
)
call venv\Scripts\activate.bat
pip install -r requirements.txt
python -m streamlit run app.py
pause
```

Recommended startup order:

1. Double-click `start_backend.bat`.
2. Wait until the backend is running.
3. Double-click `start_frontend.bat`.

---

## 6. Environment configuration

The backend uses `.env` for configuration. Start from `.env.example`.

Common values:

```env
APP_NAME=Pump DAQ Backend
APP_ENV=development
API_PREFIX=/api
DATABASE_URL=sqlite:///./data/daq.db
DEFAULT_BAUD_RATE=9600
READ_TIMEOUT_SECONDS=1.0
```

For a local release package, SQLite is recommended because it does not require a separate database server.

---

## 7. Pairing the HC-05 on Windows

1. Turn on the Arduino and HC-05.
2. Open Windows Bluetooth settings.
3. Add a Bluetooth device.
4. Select the HC-05 module.
5. Enter the pairing PIN if prompted. Common default pins are `1234` or `0000`.
6. Open Device Manager.
7. Check **Ports (COM & LPT)** and note the COM port assigned to the HC-05.

The dashboard can use Auto-detect, but knowing the COM port is useful for troubleshooting.

---

## 8. Connecting from the dashboard

1. Start the backend.
2. Start the frontend.
3. Open the dashboard sidebar.
4. Expand **HC-05 / serial connection**.
5. Keep baud rate at `9600`, unless the Arduino uses a different value.
6. Click **Auto-detect**.
7. If Auto-detect fails, choose the COM port manually and click **Connect**.
8. Confirm that the connection status changes to connected.

Use `SIMULATOR` as the selected port if testing without physical hardware.

---

## 9. Arduino output format

The Arduino should print one CSV line per sample using this order:

```text
timer,flow_l_hr,p1_suction,p1_discharge,p2_suction,p2_discharge
```

Example:

```text
12,318.0,8.2,12.7,11.9,16.4
```

Important notes:

- Do not print extra labels on every line.
- Do not change the field order unless the backend parser is updated.
- Make sure the baud rate in Arduino matches the dashboard/backend baud rate.
- If a header is printed once during Arduino startup, the backend will ignore it.

---

## 10. Verifying the system with simulator mode

Simulator mode is the fastest way to confirm that the backend and frontend are installed correctly.

1. Start the backend.
2. Start the frontend.
3. Open **HC-05 / serial connection** in the sidebar.
4. Select `SIMULATOR`.
5. Click **Connect**.
6. Go to **Live Dashboard** and check if readings appear.
7. Start and stop a recording session.
8. Go to **Load Session**.
9. Select the saved session and click **Load selected session**.
10. Confirm that the summary, graphs, table, and CSV download are shown.

---

## 11. Recording a real session

1. Pair the HC-05 with the computer.
2. Start backend and frontend.
3. Connect to the HC-05 from the sidebar.
4. Select pump mode: **Series** or **Parallel**.
5. Enter a session name.
6. Click **Start recording**.
7. Run the pump experiment.
8. Click **Stop recording**.
9. Open **Load Session**.
10. Load the recorded session and review the results.
11. Click **Download selected CSV** if a copy of the data is needed.

---

## 12. Generated data files

The backend stores local data in its `data/` folder, including:

- SQLite database file
- Session CSV files

For a clean release repository, these files should normally be ignored by Git unless they are intentional demo files.

Recommended `.gitignore` entries:

```gitignore
venv/
__pycache__/
*.pyc
.env
data/
.streamlit/secrets.toml
```

---

## 13. Troubleshooting

### `python` is not recognized

Install Python and make sure it is added to PATH. On Windows, the Python installer has an **Add python.exe to PATH** checkbox.

### `streamlit` is not recognized

Run Streamlit through Python:

```bash
python -m streamlit run app.py
```

Also confirm that the frontend virtual environment is activated and that requirements were installed.

### Frontend cannot connect to backend

Check that the backend terminal is running and that the URL is:

```text
http://127.0.0.1:8000
```

Then check the backend URL field in the dashboard sidebar.

### HC-05 Auto-detect fails

Try the following:

- Confirm that HC-05 is paired with the computer.
- Restart the Arduino.
- Restart the backend.
- Select the COM port manually.
- Check that no other program, such as Arduino Serial Monitor, is using the COM port.
- Confirm that the baud rate matches the Arduino sketch.

### Backend connects but no samples appear

Check the Arduino serial output. It should match:

```text
timer,flow_l_hr,p1_suction,p1_discharge,p2_suction,p2_discharge
```

Use the FastAPI docs page to check:

```text
GET /api/serial/status
GET /api/serial/latest
GET /api/live/recent
```

### Load Session has no sessions

A session appears only after a recording has been started and stopped, or after a manual-input session has been saved.

### CSV download does not work

Go to **Load Session**, select a saved session, then use **Download selected CSV**. The CSV download is no longer located in **Sessions & Comparison**.

---
