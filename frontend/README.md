# Pump DAQ Streamlit Frontend

This Streamlit dashboard is aligned with the DAQ fields currently expected from the Arduino/backend:

```txt
timer
flow_l_hr
p1_suction
p1_discharge
p2_suction
p2_discharge
```

## Included features

- Pump mode selector: Series and Parallel
- Start/stop recording
- Reset visible live readings
- Timer display
- Flow rate display
- Computed head
- Pump 1 suction/discharge pressure
- Pump 2 suction/discharge pressure
- Live pressure graph over time
- Live flow and head graph over time
- Head vs. flow pump performance curve
- Session list
- Session comparison
- CSV export link
- Mock-data fallback when backend is not running
- COM/HC-05 connect, disconnect, and auto-detect controls
- Manual Input tab using average live flow and manually entered pressures

## Expected backend API

The frontend expects the backend to expose:

```txt
GET    /api/health
GET    /api/live/recent?limit=300
GET    /api/serial/ports
GET    /api/serial/status
POST   /api/serial/connect
POST   /api/serial/auto-connect
POST   /api/serial/disconnect
POST   /api/sessions/start
POST   /api/sessions/stop
GET    /api/sessions
GET    /api/sessions/{session_id}/samples
GET    /api/sessions/{session_id}/export
```

## Expected sample format

```json
{
  "timer": 12,
  "flow_l_hr": 1250.2,
  "p1_suction": 10.1,
  "p1_discharge": 24.7,
  "p2_suction": 23.9,
  "p2_discharge": 38.4,
  "pump_mode": "series",
  "timestamp": "2026-05-29T17:30:00+08:00",
  "is_recording": true,
  "session_id": "abc123"
}
```

Only the six main DAQ fields are required. The dashboard can still run if `timestamp`, `pump_mode`, `is_recording`, or `session_id` are missing.


## Run

```bash
pip install -r requirements.txt
python -m streamlit run app.py
```

or:

```bash
py -m streamlit run app.py
```

On Windows, you can also double-click:

```txt
run_dashboard.bat
```

## Backend URL

Default backend URL:

```txt
http://localhost:8000
```

You can change this in the Streamlit sidebar.
