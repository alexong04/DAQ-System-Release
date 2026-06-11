from datetime import datetime, timezone
from typing import Optional

from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class DAQSession(SQLModel, table=True):
    """A recorded pump-test session."""

    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True)
    pump_mode: str = Field(index=True)
    notes: Optional[str] = None
    started_at: datetime = Field(default_factory=utc_now, index=True)
    ended_at: Optional[datetime] = Field(default=None, index=True)
    sample_count: int = 0
    csv_path: Optional[str] = None


class SensorSample(SQLModel, table=True):
    """One time-series data point from the Arduino/HC-05 stream."""

    id: Optional[int] = Field(default=None, primary_key=True)
    session_id: Optional[int] = Field(default=None, foreign_key="daqsession.id", index=True)
    timestamp: datetime = Field(default_factory=utc_now, index=True)
    pump_mode: str = Field(default="series", index=True)

    # Fields sent by Arduino:
    # timer,flow_l_hr,p1_suction,p1_discharge,p2_suction,p2_discharge
    timer: Optional[float] = Field(default=None, index=True)
    flow_l_hr: Optional[float] = None
    p1_suction: Optional[float] = None
    p1_discharge: Optional[float] = None
    p2_suction: Optional[float] = None
    p2_discharge: Optional[float] = None

    # Backend-computed fields.
    flow_l_min: Optional[float] = None
    flow_m3_s: Optional[float] = None
    delta_pressure_psi: Optional[float] = None
    head_ft: Optional[float] = None
    hydraulic_power_w: Optional[float] = None

    raw_line: Optional[str] = None
    is_valid: bool = True
    parse_error: Optional[str] = None
