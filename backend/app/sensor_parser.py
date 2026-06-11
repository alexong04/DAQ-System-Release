import json
import re
from dataclasses import dataclass
from typing import Dict, Optional


@dataclass
class ParsedSensorLine:
    values: Dict[str, Optional[float]]
    is_valid: bool
    error: Optional[str] = None


ALIASES = {
    # Timer / elapsed time from Arduino.
    "timer": "timer",
    "time": "timer",
    "t": "timer",
    "elapsed": "timer",
    "elapsed_s": "timer",
    "seconds": "timer",
    "sec": "timer",
    "millis": "timer",

    # Flow in liters per hour.
    "flow": "flow_l_hr",
    "flow_l_hr": "flow_l_hr",
    "flow_lhr": "flow_l_hr",
    "flow_lh": "flow_l_hr",
    "flow_l_per_hr": "flow_l_hr",
    "lhr": "flow_l_hr",

    # Pump 1 suction/discharge.
    "p1_suction": "p1_suction",
    "p1suction": "p1_suction",
    "p1_suc": "p1_suction",
    "p1s": "p1_suction",
    "p1_inlet": "p1_suction",
    "p1inlet": "p1_suction",
    "p1_discharge": "p1_discharge",
    "p1discharge": "p1_discharge",
    "p1_dis": "p1_discharge",
    "p1d": "p1_discharge",
    "p1_outlet": "p1_discharge",
    "p1outlet": "p1_discharge",

    # Pump 2 suction/discharge.
    "p2_suction": "p2_suction",
    "p2suction": "p2_suction",
    "p2_suc": "p2_suction",
    "p2s": "p2_suction",
    "p2_inlet": "p2_suction",
    "p2inlet": "p2_suction",
    "p2_discharge": "p2_discharge",
    "p2discharge": "p2_discharge",
    "p2_dis": "p2_discharge",
    "p2d": "p2_discharge",
    "p2_outlet": "p2_discharge",
    "p2outlet": "p2_discharge",
}

DEFAULT_VALUES = {
    "timer": None,
    "flow_l_hr": None,
    "p1_suction": None,
    "p1_discharge": None,
    "p2_suction": None,
    "p2_discharge": None,
}


def _to_float(value) -> Optional[float]:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).strip()
    if text == "":
        return None
    return float(text)


def _parse_json_line(line: str) -> ParsedSensorLine:
    payload = json.loads(line)
    if not isinstance(payload, dict):
        raise ValueError("JSON line must be an object.")

    values = DEFAULT_VALUES.copy()
    for key, value in payload.items():
        normalized = ALIASES.get(str(key).strip().lower())
        if normalized:
            values[normalized] = _to_float(value)

    if all(v is None for v in values.values()):
        return ParsedSensorLine(values=values, is_valid=False, error="No recognized sensor fields in JSON.")
    return ParsedSensorLine(values=values, is_valid=True)


def _parse_key_value_line(line: str) -> ParsedSensorLine:
    # Supports: timer:1,flow_l_hr:300,p1_suction:8,p1_discharge:12,p2_suction:11,p2_discharge:16
    pairs = re.findall(r"([A-Za-z0-9_]+)\s*[:=]\s*(-?\d+(?:\.\d+)?)", line)
    if not pairs:
        raise ValueError("No key-value pairs found.")

    values = DEFAULT_VALUES.copy()
    for key, value in pairs:
        normalized = ALIASES.get(key.strip().lower())
        if normalized:
            values[normalized] = _to_float(value)

    if all(v is None for v in values.values()):
        return ParsedSensorLine(values=values, is_valid=False, error="No recognized sensor fields in key-value line.")
    return ParsedSensorLine(values=values, is_valid=True)


def _parse_csv_line(line: str) -> ParsedSensorLine:
    # Final Arduino CSV order:
    #   timer,flow_l_hr,p1_suction,p1_discharge,p2_suction,p2_discharge
    # A 5-field no-timer fallback is also accepted:
    #   flow_l_hr,p1_suction,p1_discharge,p2_suction,p2_discharge
    parts = [p.strip() for p in line.split(",")]

    # If Arduino accidentally prints the CSV header once, skip it instead of crashing.
    if any(re.search(r"[A-Za-z]", part) for part in parts):
        return ParsedSensorLine(values=DEFAULT_VALUES.copy(), is_valid=False, error="Header/non-numeric CSV line skipped.")

    nums = [_to_float(p) for p in parts if p != ""]
    values = DEFAULT_VALUES.copy()

    if len(nums) == 6:
        (
            values["timer"],
            values["flow_l_hr"],
            values["p1_suction"],
            values["p1_discharge"],
            values["p2_suction"],
            values["p2_discharge"],
        ) = nums
    elif len(nums) == 5:
        (
            values["flow_l_hr"],
            values["p1_suction"],
            values["p1_discharge"],
            values["p2_suction"],
            values["p2_discharge"],
        ) = nums
    else:
        return ParsedSensorLine(values=values, is_valid=False, error=f"Unsupported CSV field count: {len(nums)}")

    return ParsedSensorLine(values=values, is_valid=True)


def parse_sensor_line(line: str) -> ParsedSensorLine:
    """
    Parse one Arduino/HC-05 line.

    Required final Arduino CSV format:
        timer,flow_l_hr,p1_suction,p1_discharge,p2_suction,p2_discharge

    Example:
        12,318.0,8.2,12.7,11.9,16.4

    Also accepted:
        {"timer":12,"flow_l_hr":318.0,"p1_suction":8.2,"p1_discharge":12.7,"p2_suction":11.9,"p2_discharge":16.4}
        timer:12,flow_l_hr:318.0,p1_suction:8.2,p1_discharge:12.7,p2_suction:11.9,p2_discharge:16.4
    """
    clean = line.strip()
    if not clean:
        return ParsedSensorLine(values=DEFAULT_VALUES.copy(), is_valid=False, error="Empty line.")

    try:
        if clean.startswith("{"):
            return _parse_json_line(clean)
        if ":" in clean or "=" in clean:
            return _parse_key_value_line(clean)
        return _parse_csv_line(clean)
    except Exception as exc:
        return ParsedSensorLine(values=DEFAULT_VALUES.copy(), is_valid=False, error=str(exc))
