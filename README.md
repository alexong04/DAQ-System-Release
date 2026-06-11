# Pump Data Acquisition System

A data acquisition system for recording, viewing, and comparing pump performance data from an Arduino-based hydraulic pump setup.

The system is designed for laboratory use with:

- Arduino Mega 2560
- HC-05 Bluetooth serial module
- Four 100-psi pressure sensors
- One YF-B10-S flow sensor
- FastAPI backend
- Streamlit frontend dashboard

The dashboard helps users collect live readings, record sessions, load previous sessions, compare pump performance curves, and export session data to CSV.

---

## Latest release highlights

- **Live Dashboard** for real-time flow, pressure, computed head, graphs, and readings table
- **Load Session** tab for opening an existing saved session
- **CSV download moved to Load Session** so exported files are tied to the selected loaded session
- **Sessions & Comparison** tab focused on saved-session listing and comparison curves
- **HC-05 / serial controls** with manual COM selection and Auto-detect
- **Start / Stop session recording** from the sidebar
- **Manual Input** tab for saving sessions using live flow and manually entered pressure values
- **Quizlet** tab for hidden-table-value practice using current readings, sample data, or saved sessions
- **Mock/simulator fallback** for testing the interface without hardware

---

## System architecture

```text
Arduino Mega + Sensors
        |
        | Serial data through HC-05 Bluetooth
        v
FastAPI Backend
        |
        | REST API
        v
Streamlit Frontend Dashboard
        |
        v
Saved sessions, graphs, tables, CSV exports
```

The Arduino sends one line of sensor data every sampling interval. The backend receives the line, parses the sensor values, computes engineering values, stores recorded samples, and exposes the data to the Streamlit dashboard.

---

## Expected Arduino data format

The backend expects this CSV order:

```text
timer,flow_l_hr,p1_suction,p1_discharge,p2_suction,p2_discharge
```

Example data line:

```text
12,318.0,8.2,12.7,11.9,16.4
```

Do not repeatedly print the header. If the Arduino prints the header once during startup, the backend will skip it.

Accepted fields:

| Field | Meaning |
|---|---|
| `timer` | Elapsed time or sample counter |
| `flow_l_hr` | Flow rate in liters per hour |
| `p1_suction` | Pump 1 suction pressure in psi |
| `p1_discharge` | Pump 1 discharge pressure in psi |
| `p2_suction` | Pump 2 suction pressure in psi |
| `p2_discharge` | Pump 2 discharge pressure in psi |

---

## Main dashboard tabs

| Tab | Purpose |
|---|---|
| **Live Dashboard** | Shows current live metrics, graphs, and readings table |
| **Load Session** | Loads an existing saved session, displays its summary/graphs/table, and provides CSV download |
| **Sessions & Comparison** | Lists saved sessions and compares selected sessions using the head-vs-flow curve |
| **Summary** | Shows current run summary and engineering notes |
| **Manual Input** | Uses live flow with manually entered pressure readings and saves them as a session |
| **Quizlet** | Generates hidden-value table questions from live data, sample data, or saved sessions |

---

## Backend API summary

The frontend expects the backend to expose these main endpoints:

```text
GET    /api/health
GET    /api/live/recent?limit=300
GET    /api/serial/ports
GET    /api/serial/status
POST   /api/serial/connect
POST   /api/serial/auto-connect
POST   /api/serial/disconnect
POST   /api/sessions/start
POST   /api/sessions/stop
POST   /api/sessions/manual
GET    /api/sessions
GET    /api/sessions/{session_id}/samples
GET    /api/sessions/{session_id}/summary
GET    /api/sessions/{session_id}/export
POST   /api/sessions/compare
```

---

## Quick start

### 1. Start the backend

```bash
cd backend
python -m venv venv
```

Windows PowerShell:

```powershell
venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

macOS/Linux:

```bash
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Backend URL:

```text
http://127.0.0.1:8000
```

API docs:

```text
http://127.0.0.1:8000/docs
```

### 2. Start the frontend

Open a new terminal:

```bash
cd frontend
python -m venv venv
```

Windows PowerShell:

```powershell
venv\Scripts\activate
pip install -r requirements.txt
python -m streamlit run app.py
```

macOS/Linux:

```bash
source venv/bin/activate
pip install -r requirements.txt
python -m streamlit run app.py
```

The dashboard will open in the browser.

---

## Hardware connection flow

1. Turn on the Arduino and HC-05 module.
2. Pair the HC-05 Bluetooth module with the computer.
3. Start the backend.
4. Start the frontend.
5. Open the sidebar panel named **HC-05 / serial connection**.
6. Keep baud rate at `9600` unless the Arduino uses a different value.
7. Click **Auto-detect**, or manually select the COM port and click **Connect**.
8. Confirm that the status changes to connected.
9. Start recording when ready.

For testing without hardware, select `SIMULATOR` as the serial port.

---

## Session workflow

1. Select the pump mode in the sidebar.
2. Connect to HC-05, or use simulator mode.
3. Enter a session name.
4. Click **Start recording**.
5. Watch the Live Dashboard update.
6. Click **Stop recording** when finished.
7. Open **Load Session**.
8. Select the saved session and click **Load selected session**.
9. Review the summary, graphs, and readings table.
10. Click **Download selected CSV** to export the session.

---

## Computed engineering values

The backend computes:

```text
flow_l_min = flow_l_hr / 60
```

For series mode:

```text
pressure term = (p1_discharge - p1_suction) + (p2_discharge - p2_suction)
```

For parallel mode:

```text
pressure term = average(
  p1_discharge - p1_suction,
  p2_discharge - p2_suction
)
```

Head is computed from the pressure term, velocity head, and elevation head:

```text
head_ft = ((pressure term × 144) / 61.4) + velocity_head_ft + 3.70735
```

The pressure-sensor mapping and velocity-head formula can be adjusted in:

```text
backend/app/calculations.py
```

---

## Notes for release

- Do not commit virtual environments such as `venv/`.
- Do not commit generated session databases or CSV files unless they are intentional demo files.
- Keep `.env.example` committed, but do not commit private `.env` files.
- Test the system once with `SIMULATOR` mode.
- Test the system once with the actual HC-05 connection.
- Confirm that Load Session can load and export a recorded session.

---

## Troubleshooting

### Frontend says backend is offline

Make sure the backend is running at:

```text
http://127.0.0.1:8000
```

Then check the backend URL field in the Streamlit sidebar.

### HC-05 is not detected

- Pair the HC-05 with Windows first.
- Confirm the COM port in Device Manager.
- Try Auto-detect.
- Try manually selecting the COM port.
- Confirm that Arduino and backend use the same baud rate.

### No live data appears

- Make sure the backend is connected to the correct COM port.
- Check that the Arduino is printing the expected CSV format.
- Confirm that the backend serial status shows received samples.
- Use `SIMULATOR` mode to verify that the dashboard works.

### Saved sessions are missing

- Sessions are created only after starting and stopping a recording.
- Check that the backend has write access to its `data/` directory.
- Do not delete the backend database or session CSV folder unless intentionally resetting data.

---

