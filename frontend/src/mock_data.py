from __future__ import annotations

import math
import random
from datetime import datetime

from src.engineering import normalize_sample


def _mode_baselines(mode: str) -> tuple[float, float]:
    if mode == "parallel":
        return 1650.0, 16.0
    return 1120.0, 28.0


def generate_mock_sample(mode: str, index: int, is_recording: bool = False) -> dict:
    flow_base, head_psi_base = _mode_baselines(mode)

    timer = float(index)
    flow = flow_base + math.sin(index / 9.0) * 90.0 + random.uniform(-35.0, 35.0)

    p1_suction = 8.0 + random.uniform(-0.35, 0.35)

    if mode == "series":
        p1_discharge = p1_suction + 14.0 + math.sin(index / 10.0)
        p2_suction = p1_discharge - random.uniform(0.2, 0.8)
        p2_discharge = p1_suction + head_psi_base + math.cos(index / 11.0) * 2.0
    else:
        p1_discharge = p1_suction + head_psi_base + math.sin(index / 10.0)
        p2_suction = p1_suction + random.uniform(-0.4, 0.4)
        p2_discharge = p2_suction + head_psi_base + math.cos(index / 11.0)

    sample = {
        "timestamp": datetime.now().isoformat(),
        "timer": timer,
        "flow_l_hr": max(0.0, flow),
        "p1_suction": max(0.0, p1_suction),
        "p1_discharge": max(0.0, p1_discharge),
        "p2_suction": max(0.0, p2_suction),
        "p2_discharge": max(0.0, p2_discharge),
        "pump_mode": mode,
        "is_recording": is_recording,
        "session_id": "mock-session" if is_recording else None,
    }

    return normalize_sample(sample, mode)


def ensure_mock_history(session_state, mode: str, is_recording: bool, limit: int = 300) -> list[dict]:
    if "mock_samples" not in session_state:
        session_state.mock_samples = []

    if "mock_index" not in session_state:
        session_state.mock_index = 0

    session_state.mock_index += 1
    session_state.mock_samples.append(
        generate_mock_sample(mode, session_state.mock_index, is_recording)
    )

    session_state.mock_samples = session_state.mock_samples[-limit:]
    return session_state.mock_samples
