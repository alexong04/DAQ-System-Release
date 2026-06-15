# Pump Data Acquisition Backend

FastAPI backend for the pump data acquisition system.

It supports:

- Pump mode selector: `series`, `parallel`
- Start/stop recording sessions
- Live data streaming to the frontend through WebSocket
- Computed head from pressure difference
- Flow, pressure, head, and hydraulic power storage
- CSV export per session
- Session comparison summaries
- Real serial/Bluetooth HC-05 input or a built-in simulator for frontend testing

---

## 1. Setup

```bash
cd daq-backend
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

Open API docs:

```text
http://127.0.0.1:8000/docs
```

---

## 2. Quick simulator test

Use this when the Arduino is not connected yet.

1. Start backend.
2. Open `http://127.0.0.1:8000/docs`.
3. Call:

```http
POST /api/serial/connect
```

Body:

```json
{
  "port": "SIMULATOR",
  "baud_rate": 9600
}
```

4. Start a recording session:

```http
POST /api/sessions/start
```

Body:

```json
{
  "name": "Demo Series Test",
  "pump_mode": "series",
  "notes": "Frontend test using simulated data"
}
```

5. Watch samples update through:

```text
GET /api/live/recent
GET /api/serial/latest
GET /api/sessions/{session_id}/samples
WebSocket /ws/live
```

6. Stop recording:

```http
POST /api/sessions/stop
```

---

## 3. Arduino serial output format

The backend now expects this exact CSV order from Arduino:

```text
timer,flow_l_hr,p1_suction,p1_discharge,p2_suction,p2_discharge
```

Example line sent every second:

```text
12,318.0,8.2,12.7,11.9,16.4
```

Do **not** send the header repeatedly. If you print the header once during Arduino startup, the backend will simply skip it.

JSON and key-value formats are also accepted for testing:

```json
{"timer":12,"flow_l_hr":318.0,"p1_suction":8.2,"p1_discharge":12.7,"p2_suction":11.9,"p2_discharge":16.4}
```

```text
timer:12,flow_l_hr:318.0,p1_suction:8.2,p1_discharge:12.7,p2_suction:11.9,p2_discharge:16.4
```

---

## 4. Main API endpoints

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/api/health` | Check backend status |
| GET | `/api/modes` | Get pump modes and pressure sensor mapping |
| GET | `/api/serial/ports` | List available COM/serial ports |
| POST | `/api/serial/auto-connect` | Try likely HC-05/Bluetooth COM ports and keep the first one producing data |
| POST | `/api/serial/connect` | Connect to HC-05/serial or simulator |
| POST | `/api/serial/disconnect` | Disconnect serial/simulator |
| GET | `/api/serial/status` | Get connection status |
| GET | `/api/serial/latest` | Get latest sample |
| GET | `/api/live/recent` | Get latest in-memory samples for the Streamlit dashboard |
| POST | `/api/sessions/start` | Start recording session |
| POST | `/api/sessions/stop` | Stop recording session |
| GET | `/api/sessions` | List sessions |
| GET | `/api/sessions/{id}/samples` | Load session samples |
| GET | `/api/sessions/{id}/summary` | Get computed summary |
| GET | `/api/sessions/{id}/export` | Download session CSV, used by the Streamlit frontend |
| GET | `/api/sessions/{id}/export.csv` | Download session CSV alias |
| POST | `/api/sessions/compare` | Compare sessions |
| WS | `/ws/live` | Live sample stream |

---

## 5. Output sample fields

Each live/sample response contains the Arduino fields plus backend-computed fields. Session CSV exports are intentionally cleaner and contain only the main DAQ fields, `flow_l_min`, and `head_ft`.

```json
{
  "timer": 12,
  "flow_l_hr": 318.0,
  "p1_suction": 8.2,
  "p1_discharge": 12.7,
  "p2_suction": 11.9,
  "p2_discharge": 16.4,
  "flow_l_min": 5.3,
  "delta_pressure_psi": 9.0,
  "head_ft": 24.82
}
```

---

## 6. Computed values

The backend computes:

```text
flow_l_min = flow_l_hr / 60

Series pressure term:
ΔP_psi = (p1_discharge - p1_suction) + (p2_discharge - p2_suction)

Parallel pressure term:
ΔP_psi = average(p1_discharge - p1_suction, p2_discharge - p2_suction)

Head formula:
head_ft = ((ΔP_psi * 144) / 62.4) + velocity_head_ft + 3.70735

Flow conversion:
Q_ft3_s = flow_l_hr * 0.00000980965

Default velocity-head formula with pipe area:
velocity_head_ft = ((Q_ft3_s / PIPE_AREA_FT2) ** 2) / 64.4

Optional simplified formula without pipe area:
velocity_head_ft = (Q_ft3_s ** 2) / 64.4
```

The active formula switch is in `app/calculations.py`:

```python
PIPE_INNER_DIAMETER_IN = 1.0
PIPE_AREA_FT2 = math.pi * (PIPE_INNER_DIAMETER_IN / 12.0) ** 2 / 4.0
USE_PIPE_AREA_FOR_VELOCITY_HEAD = True  # set False to use the no-pipe-area version
```

---

## 7. Pump mode pressure mapping

Edit `app/calculations.py` only if the physical schematic labels suction/discharge differently.

Current mapping:

```text
series   = p2_discharge - p1_suction
parallel = avg(p1_discharge, p2_discharge) - avg(p1_suction, p2_suction)
```
