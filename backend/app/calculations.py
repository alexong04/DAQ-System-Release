import math
from typing import Dict, Iterable, Optional, Tuple

# Flow conversion retained for future engineering use. The session CSV now stores only L/hr and L/min.
LHR_TO_M3S = 1.0 / 3_600_000.0

# Head formula constants.
# psi * 144 converts lbf/in^2 to lbf/ft^2; 62.4 is water specific weight in lbf/ft^3.
PSI_TO_LBF_PER_FT2 = 144.0
WATER_SPECIFIC_WEIGHT_LB_FT3 = 62.4
LHR_TO_FT3S = 0.00000980965
GRAVITY_2G_FT_S2 = 64.4
ELEVATION_HEAD_FT = 3.70735

# Velocity-head options.
# Default is the physically correct version: Q(ft^3/s) / pipe area(ft^2) = velocity(ft/s).
# Change PIPE_INNER_DIAMETER_IN to match the measured inside diameter of your pipe.
PIPE_INNER_DIAMETER_IN = 1.0
PIPE_AREA_FT2 = math.pi * (PIPE_INNER_DIAMETER_IN / 12.0) ** 2 / 4.0

# Switch formula here:
# True  -> velocity head = (((flow_l_hr * 0.00000980965) / PIPE_AREA_FT2) ** 2) / 64.4
# False -> velocity head = ((flow_l_hr * 0.00000980965) ** 2) / 64.4
USE_PIPE_AREA_FOR_VELOCITY_HEAD = True

# Sensor names now match the fields sent by Arduino:
# timer,flow_l_hr,p1_suction,p1_discharge,p2_suction,p2_discharge
#
# Adjust only this map if the physical schematic labels suction/discharge differently.
# The rest of the backend will continue to work.
PUMP_MODE_SENSOR_MAP: Dict[str, Dict[str, object]] = {
    "series": {
        "label": "Series Pumps",
        "inlet": ["p1_suction", "p2_suction"],
        "outlet": ["p1_discharge", "p2_discharge"],
        "description": "Uses the combined pump pressure rise: (p1_discharge - p1_suction) + (p2_discharge - p2_suction).",
    },
    "parallel": {
        "label": "Parallel Pumps",
        "inlet": ["p1_suction", "p2_suction"],
        "outlet": ["p1_discharge", "p2_discharge"],
        "description": "Uses the average pressure rise produced by Pump 1 and Pump 2.",
    },
}

DEFAULT_PUMP_MODE = "series"


def lhr_to_lmin(flow_l_hr: Optional[float]) -> Optional[float]:
    if flow_l_hr is None:
        return None
    return flow_l_hr / 60.0


def lhr_to_m3s(flow_l_hr: Optional[float]) -> Optional[float]:
    if flow_l_hr is None:
        return None
    return flow_l_hr * LHR_TO_M3S


def _pressure_delta(values: Dict[str, Optional[float]], discharge_key: str, suction_key: str) -> Optional[float]:
    discharge = values.get(discharge_key)
    suction = values.get(suction_key)
    if discharge is None or suction is None:
        return None
    return discharge - suction


def _mean_available(items: Iterable[Optional[float]]) -> Optional[float]:
    nums = [value for value in items if value is not None]
    if not nums:
        return None
    return sum(nums) / len(nums)


def compute_delta_pressure_psi(pump_mode: str, values: Dict[str, Optional[float]]) -> Tuple[Optional[float], Optional[str]]:
    """
    Compute the pressure-rise term used by the selected pump mode.

    Series: (p1_discharge - p1_suction) + (p2_discharge - p2_suction)
    Parallel: average of Pump 1 pressure rise and Pump 2 pressure rise

    Returns: (delta_pressure_psi, warning_message)
    """
    mode = pump_mode if pump_mode in PUMP_MODE_SENSOR_MAP else DEFAULT_PUMP_MODE

    pump_1_delta = _pressure_delta(values, "p1_discharge", "p1_suction")
    pump_2_delta = _pressure_delta(values, "p2_discharge", "p2_suction")

    if mode == "series":
        if pump_1_delta is not None and pump_2_delta is not None:
            return pump_1_delta + pump_2_delta, None

        fallback_inlet = values.get("p1_suction")
        fallback_outlet = values.get("p2_discharge")
        if fallback_inlet is not None and fallback_outlet is not None:
            return fallback_outlet - fallback_inlet, (
                "Missing one or more series pump pressure fields; used fallback p2_discharge - p1_suction."
            )
        return None, "Missing pressure values required for series mode."

    if mode == "parallel":
        average_delta = _mean_available([pump_1_delta, pump_2_delta])
        if average_delta is not None:
            return average_delta, None
        return None, "Missing pressure values required for parallel mode."

    return None, f"Unsupported pump mode: {pump_mode}."


def flow_lhr_to_ft3s(flow_l_hr: Optional[float]) -> Optional[float]:
    if flow_l_hr is None:
        return None
    return flow_l_hr * LHR_TO_FT3S


def velocity_head_ft_with_pipe_area(flow_l_hr: Optional[float]) -> Optional[float]:
    """Velocity head using v = Q / A, where Q is ft^3/s and A is pipe area in ft^2."""
    flow_ft3_s = flow_lhr_to_ft3s(flow_l_hr)
    if flow_ft3_s is None or PIPE_AREA_FT2 <= 0:
        return None
    velocity_ft_s = flow_ft3_s / PIPE_AREA_FT2
    return (velocity_ft_s ** 2) / GRAVITY_2G_FT_S2


def velocity_head_ft_without_pipe_area(flow_l_hr: Optional[float]) -> Optional[float]:
    """Simplified velocity term if you want to use Q^2 / 2g directly without pipe area."""
    flow_ft3_s = flow_lhr_to_ft3s(flow_l_hr)
    if flow_ft3_s is None:
        return None
    return (flow_ft3_s ** 2) / GRAVITY_2G_FT_S2


def velocity_head_ft(flow_l_hr: Optional[float]) -> Optional[float]:
    """Active velocity-head formula. Comment/uncomment the return lines below to switch versions."""
    if USE_PIPE_AREA_FOR_VELOCITY_HEAD:
        return velocity_head_ft_with_pipe_area(flow_l_hr)
    return velocity_head_ft_without_pipe_area(flow_l_hr)

    # Manual switch alternative:
    # return velocity_head_ft_with_pipe_area(flow_l_hr)
    # return velocity_head_ft_without_pipe_area(flow_l_hr)


def compute_head_ft(delta_pressure_psi: Optional[float], flow_l_hr: Optional[float]) -> Optional[float]:
    """Compute total head in feet: pressure head + velocity head + elevation head."""
    if delta_pressure_psi is None:
        return None
    pressure_term_ft = (delta_pressure_psi * PSI_TO_LBF_PER_FT2) / WATER_SPECIFIC_WEIGHT_LB_FT3
    velocity_term_ft = velocity_head_ft(flow_l_hr) or 0.0
    return pressure_term_ft + velocity_term_ft + ELEVATION_HEAD_FT


def compute_engineering_values(pump_mode: str, values: Dict[str, Optional[float]]) -> Dict[str, Optional[float]]:
    flow_l_hr = values.get("flow_l_hr")
    flow_l_min = lhr_to_lmin(flow_l_hr)
    flow_m3_s = lhr_to_m3s(flow_l_hr)
    delta_psi, _ = compute_delta_pressure_psi(pump_mode, values)
    head_ft = compute_head_ft(delta_psi, flow_l_hr)

    return {
        "flow_l_min": flow_l_min,
        "flow_m3_s": flow_m3_s,
        "delta_pressure_psi": delta_psi,
        "head_ft": head_ft,
        "hydraulic_power_w": None,
    }


def format_sensor_keys(keys: Iterable[str]) -> str:
    return ", ".join(keys)
