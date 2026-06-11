from datetime import datetime
from typing import List, Literal, Optional

from pydantic import BaseModel, Field

PumpMode = Literal["series", "parallel"]


class ModeInfo(BaseModel):
    key: PumpMode
    label: str
    inlet_sensor: str
    outlet_sensor: str
    description: str


class SerialConnectRequest(BaseModel):
    port: str = Field(..., examples=["COM4", "/dev/tty.HC-05-DevB", "SIMULATOR"])
    baud_rate: int = Field(default=9600, ge=300, le=230400)


class SerialAutoConnectRequest(BaseModel):
    baud_rate: int = Field(default=9600, ge=300, le=230400)
    probe_seconds: float = Field(default=3.0, ge=0.5, le=10.0)
    port_hints: Optional[List[str]] = Field(default=None)


class SerialStatus(BaseModel):
    connected: bool
    port: Optional[str] = None
    baud_rate: Optional[int] = None
    mode: str = "idle"
    last_line: Optional[str] = None
    last_error: Optional[str] = None
    samples_received: int = 0


class StartSessionRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    pump_mode: PumpMode
    notes: Optional[str] = Field(default=None, max_length=1000)


class StopSessionResponse(BaseModel):
    id: int
    name: str
    pump_mode: str
    started_at: datetime
    ended_at: Optional[datetime]
    sample_count: int
    csv_path: Optional[str]


class DAQSessionRead(BaseModel):
    id: int
    name: str
    pump_mode: str
    notes: Optional[str]
    started_at: datetime
    ended_at: Optional[datetime]
    sample_count: int
    csv_path: Optional[str]


class SensorSampleRead(BaseModel):
    id: Optional[int] = None
    session_id: Optional[int] = None
    timestamp: datetime
    pump_mode: str

    # Same names as the Arduino CSV fields.
    timer: Optional[float] = None
    flow_l_hr: Optional[float] = None
    p1_suction: Optional[float] = None
    p1_discharge: Optional[float] = None
    p2_suction: Optional[float] = None
    p2_discharge: Optional[float] = None

    # Computed by the backend.
    flow_l_min: Optional[float] = None
    flow_m3_s: Optional[float] = None
    delta_pressure_psi: Optional[float] = None
    head_ft: Optional[float] = None
    hydraulic_power_w: Optional[float] = None

    raw_line: Optional[str] = None
    is_valid: bool = True
    parse_error: Optional[str] = None


class SessionSummary(BaseModel):
    session_id: int
    name: str
    pump_mode: str
    sample_count: int
    started_at: datetime
    ended_at: Optional[datetime]
    avg_flow_l_hr: Optional[float]
    max_flow_l_hr: Optional[float]
    avg_head_ft: Optional[float]
    max_head_ft: Optional[float]
    avg_delta_pressure_psi: Optional[float]
    max_delta_pressure_psi: Optional[float]
    avg_hydraulic_power_w: Optional[float]
    max_hydraulic_power_w: Optional[float]


class CompareSessionsRequest(BaseModel):
    session_ids: List[int] = Field(..., min_length=1, max_length=12)


class CompareSessionsResponse(BaseModel):
    summaries: List[SessionSummary]


class ApiMessage(BaseModel):
    message: str


class PortInfo(BaseModel):
    device: str
    description: str
    hwid: Optional[str] = None


class LivePayload(BaseModel):
    type: str = "sample"
    data: SensorSampleRead


class ModeSensorMapResponse(BaseModel):
    modes: List[ModeInfo]
    note: str
