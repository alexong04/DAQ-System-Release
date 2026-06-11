DEFAULT_BACKEND_URL = "http://localhost:8000"

APP_TITLE = "Pump Performance Dashboard"
APP_SUBTITLE = (
    "Monitor timer, flow rate, suction pressure, discharge pressure, "
    "computed head, and pump performance curves for series and parallel pump configurations."
)

RECENT_SAMPLE_LIMIT = 300

DAQ_FIELDS = [
    "timer",
    "flow_l_hr",
    "p1_suction",
    "p1_discharge",
    "p2_suction",
    "p2_discharge",
]

PRESSURE_COLUMNS = [
    "p1_suction",
    "p1_discharge",
    "p2_suction",
    "p2_discharge",
]
