from __future__ import annotations

from datetime import datetime
import math
from typing import Any

import pandas as pd

from src.pump_modes import get_mode

PSI_TO_LBF_PER_FT2 = 144.0
WATER_SPECIFIC_WEIGHT_LB_FT3 = 62.4
LHR_TO_FT3S = 0.00000980965
GRAVITY_2G_FT_S2 = 64.4
ELEVATION_HEAD_FT = 3.70735

# Keep these constants aligned with backend app/calculations.py.
# Change PIPE_INNER_DIAMETER_IN to match the measured inside diameter of your pipe.
PIPE_INNER_DIAMETER_IN = 1.0
PIPE_AREA_FT2 = math.pi * (PIPE_INNER_DIAMETER_IN / 12.0) ** 2 / 4.0

# Switch formula here:
# True  -> velocity head = (((flow_l_hr * 0.00000980965) / PIPE_AREA_FT2) ** 2) / 64.4
# False -> velocity head = ((flow_l_hr * 0.00000980965) ** 2) / 64.4
USE_PIPE_AREA_FOR_VELOCITY_HEAD = False


def safe_float(value: Any, fallback: float = 0.0) -> float:
    try:
        if value is None or value == "":
            return fallback
        return float(value)
    except (TypeError, ValueError):
        return fallback


def flow_lhr_to_ft3s(flow_l_hr: float) -> float:
    return flow_l_hr * LHR_TO_FT3S


def velocity_head_ft_with_pipe_area(flow_l_hr: float) -> float:
    """Velocity head using v = Q / A, where Q is ft^3/s and A is pipe area in ft^2."""
    if PIPE_AREA_FT2 <= 0:
        return 0.0
    flow_ft3_s = flow_lhr_to_ft3s(flow_l_hr)
    velocity_ft_s = flow_ft3_s / PIPE_AREA_FT2
    return (velocity_ft_s ** 2) / GRAVITY_2G_FT_S2


def velocity_head_ft_without_pipe_area(flow_l_hr: float) -> float:
    """Simplified velocity term if you want to use Q^2 / 2g directly without pipe area."""
    flow_ft3_s = flow_lhr_to_ft3s(flow_l_hr)
    return (flow_ft3_s ** 2) / GRAVITY_2G_FT_S2


def velocity_head_ft(flow_l_hr: float) -> float:
    """Active velocity-head formula. Comment/uncomment the return lines below to switch versions."""
    if USE_PIPE_AREA_FOR_VELOCITY_HEAD:
        return velocity_head_ft_with_pipe_area(flow_l_hr)
    return velocity_head_ft_without_pipe_area(flow_l_hr)

    # Manual switch alternative:
    # return velocity_head_ft_with_pipe_area(flow_l_hr)
    # return velocity_head_ft_without_pipe_area(flow_l_hr)


def compute_head_ft_from_delta_and_flow(delta_psi: float, flow_l_hr: float) -> float:
    pressure_head_ft = (delta_psi * PSI_TO_LBF_PER_FT2) / WATER_SPECIFIC_WEIGHT_LB_FT3
    return max(0.0, pressure_head_ft + velocity_head_ft(flow_l_hr) + ELEVATION_HEAD_FT)


def compute_delta_psi(sample: dict, selected_mode: str = "series") -> float:
    mode = get_mode(sample.get("pump_mode") or selected_mode)
    strategy = mode.get("head_strategy", "series")

    p1_suction = safe_float(sample.get("p1_suction"))
    p1_discharge = safe_float(sample.get("p1_discharge"))
    p2_suction = safe_float(sample.get("p2_suction"))
    p2_discharge = safe_float(sample.get("p2_discharge"))

    pump_1_delta = p1_discharge - p1_suction
    pump_2_delta = p2_discharge - p2_suction

    if strategy == "series":
        delta_psi = pump_1_delta + pump_2_delta
    elif strategy == "parallel":
        delta_psi = (pump_1_delta + pump_2_delta) / 2
    else:
        delta_psi = pump_1_delta + pump_2_delta

    return max(0.0, delta_psi)


def compute_head_feet(sample: dict, selected_mode: str = "series") -> float:
    backend_head = sample.get("head_ft")
    if backend_head is not None:
        return max(0.0, safe_float(backend_head))

    delta_psi = compute_delta_psi(sample, selected_mode)
    flow_l_hr = safe_float(sample.get("flow_l_hr"))
    return compute_head_ft_from_delta_and_flow(delta_psi, flow_l_hr)


def normalize_sample(sample: dict | None, selected_mode: str = "series") -> dict:
    sample = sample or {}

    normalized = {
        "timestamp": sample.get("timestamp") or datetime.now().isoformat(),
        "timer": safe_float(sample.get("timer")),
        "flow_l_hr": safe_float(sample.get("flow_l_hr")),
        "p1_suction": safe_float(sample.get("p1_suction")),
        "p1_discharge": safe_float(sample.get("p1_discharge")),
        "p2_suction": safe_float(sample.get("p2_suction")),
        "p2_discharge": safe_float(sample.get("p2_discharge")),
        "pump_mode": sample.get("pump_mode") or selected_mode,
        "is_recording": bool(sample.get("is_recording", False)),
        "session_id": sample.get("session_id"),
    }

    normalized["head_ft"] = compute_head_feet({**sample, **normalized}, selected_mode)
    return normalized


def samples_to_dataframe(samples: list[dict], selected_mode: str = "series") -> pd.DataFrame:
    normalized_samples = [normalize_sample(sample, selected_mode) for sample in samples]
    df = pd.DataFrame(normalized_samples)

    columns = [
        "timestamp",
        "time",
        "timer",
        "pump_mode",
        "flow_l_hr",
        "head_ft",
        "p1_suction",
        "p1_discharge",
        "p2_suction",
        "p2_discharge",
        "is_recording",
        "session_id",
    ]

    if df.empty:
        return pd.DataFrame(columns=columns)

    df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
    df["time"] = df["timestamp"].dt.strftime("%H:%M:%S")

    numeric_cols = [
        "timer",
        "flow_l_hr",
        "head_ft",
        "p1_suction",
        "p1_discharge",
        "p2_suction",
        "p2_discharge",
    ]

    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)

    return df[columns]


def summarize_dataframe(df: pd.DataFrame) -> dict:
    if df.empty:
        return {
            "sample_count": 0,
            "latest_timer": 0.0,
            "avg_flow_l_hr": 0.0,
            "max_flow_l_hr": 0.0,
            "avg_head_ft": 0.0,
            "max_head_ft": 0.0,
            "min_head_ft": 0.0,
        }

    return {
        "sample_count": int(len(df)),
        "latest_timer": float(df["timer"].iloc[-1]),
        "avg_flow_l_hr": float(df["flow_l_hr"].mean()),
        "max_flow_l_hr": float(df["flow_l_hr"].max()),
        "avg_head_ft": float(df["head_ft"].mean()),
        "max_head_ft": float(df["head_ft"].max()),
        "min_head_ft": float(df["head_ft"].min()),
    }


def format_number(value: Any, decimals: int = 2) -> str:
    try:
        return f"{float(value):,.{decimals}f}"
    except (TypeError, ValueError):
        return "—"


def format_integer(value: Any) -> str:
    try:
        return f"{float(value):,.0f}"
    except (TypeError, ValueError):
        return "—"
