PUMP_MODES = {
    "series": {
        "label": "Series Pumps",
        "short_label": "Series",
        "description": (
            "Two pumps are arranged one after another. The total system head estimate uses the combined pressure rise across Pump 1 and Pump 2."
        ),
        "head_strategy": "series",
        "formula": "Head (ft) = (((P1 ΔP + P2 ΔP) × 144) / 62.4) + velocity head + 3.70735",
        "badge": "S",
    },
    "parallel": {
        "label": "Parallel Pumps",
        "short_label": "Parallel",
        "description": (
            "Two pumps operate on parallel paths. The estimate uses the average pressure rise produced by Pump 1 and Pump 2."
        ),
        "head_strategy": "parallel",
        "formula": "Head (ft) = (((avg(P1 ΔP, P2 ΔP)) × 144) / 62.4) + velocity head + 3.70735",
        "badge": "P",
    },
}

DEFAULT_PUMP_MODE = "series"


def get_mode_options():
    return list(PUMP_MODES.keys())


def get_mode_label(mode_id: str) -> str:
    return PUMP_MODES.get(mode_id, PUMP_MODES[DEFAULT_PUMP_MODE])["label"]


def get_mode(mode_id: str) -> dict:
    return PUMP_MODES.get(mode_id, PUMP_MODES[DEFAULT_PUMP_MODE])
