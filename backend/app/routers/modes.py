from fastapi import APIRouter

from app.calculations import PUMP_MODE_SENSOR_MAP
from app.schemas import ModeInfo, ModeSensorMapResponse

router = APIRouter(prefix="/modes", tags=["modes"])


def _format_sensor_list(value) -> str:
    if isinstance(value, list):
        if len(value) == 1:
            return value[0]
        return "avg(" + ", ".join(value) + ")"
    return str(value)


@router.get("", response_model=ModeSensorMapResponse)
def list_modes():
    modes = []
    for key, item in PUMP_MODE_SENSOR_MAP.items():
        modes.append(
            ModeInfo(
                key=key,
                label=item["label"],
                inlet_sensor=_format_sensor_list(item["inlet"]),
                outlet_sensor=_format_sensor_list(item["outlet"]),
                description=item["description"],
            )
        )

    return ModeSensorMapResponse(
        modes=modes,
        note="Backend expects Arduino CSV fields in this exact order: timer,flow_l_hr,p1_suction,p1_discharge,p2_suction,p2_discharge. If the physical labels change, update PUMP_MODE_SENSOR_MAP in app/calculations.py.",
    )
