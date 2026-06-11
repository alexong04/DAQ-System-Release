from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlmodel import Session

from app.calculations import compute_engineering_values
from app.config import get_settings
from app.database import engine
from app.models import DAQSession, SensorSample
from app.schemas import (
    ApiMessage,
    CompareSessionsRequest,
    CompareSessionsResponse,
    DAQSessionRead,
    PumpMode,
    SensorSampleRead,
    StartSessionRequest,
    StopSessionResponse,
)
from app.services.session_service import session_service

router = APIRouter(prefix="/sessions", tags=["sessions"])


class ManualSampleInput(BaseModel):
    timestamp: str | None = None
    timer: float | None = None
    flow_l_hr: float | None = None
    p1_suction: float | None = None
    p1_discharge: float | None = None
    p2_suction: float | None = None
    p2_discharge: float | None = None


class SaveManualSessionRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)
    pump_mode: PumpMode
    notes: str | None = Field(default=None, max_length=1000)
    samples: list[ManualSampleInput] = Field(..., min_length=1, max_length=5000)


def _export_session_file(session_id: int):
    path = session_service.get_csv_path(session_id)
    if not path:
        raise HTTPException(status_code=404, detail="CSV export not found for this session.")
    return FileResponse(
        path=str(path),
        media_type="text/csv",
        filename=path.name,
    )


def _parse_timestamp(value: str | None):
    if not value:
        return None
    try:
        from datetime import datetime

        cleaned = str(value).replace("Z", "+00:00")
        return datetime.fromisoformat(cleaned)
    except (TypeError, ValueError):
        return None


@router.post("/start", response_model=DAQSessionRead)
def start_session(request: StartSessionRequest):
    try:
        return session_service.start_session(
            name=request.name,
            pump_mode=request.pump_mode,
            notes=request.notes,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/manual", response_model=DAQSessionRead)
def save_manual_session(request: SaveManualSessionRequest):
    """Save the Live flow + manual pressure appended table as a closed session."""
    settings = get_settings()

    with Session(engine) as db:
        daq_session = DAQSession(
            name=request.name.strip(),
            pump_mode=request.pump_mode,
            notes=request.notes or "Saved from the Live flow + manual pressure tab.",
        )
        db.add(daq_session)
        db.commit()
        db.refresh(daq_session)

        csv_path = settings.sessions_dir / f"session_{daq_session.id:04d}.csv"
        session_service._initialize_csv(csv_path)
        daq_session.csv_path = str(csv_path)

        persisted_samples: list[SensorSample] = []
        for index, row in enumerate(request.samples, start=1):
            values = {
                "flow_l_hr": row.flow_l_hr,
                "p1_suction": row.p1_suction,
                "p1_discharge": row.p1_discharge,
                "p2_suction": row.p2_suction,
                "p2_discharge": row.p2_discharge,
            }
            computed = compute_engineering_values(request.pump_mode, values)

            sample = SensorSample(
                session_id=daq_session.id,
                pump_mode=request.pump_mode,
                timestamp=_parse_timestamp(row.timestamp) or daq_session.started_at,
                timer=row.timer if row.timer is not None else float(index),
                flow_l_hr=row.flow_l_hr,
                p1_suction=row.p1_suction,
                p1_discharge=row.p1_discharge,
                p2_suction=row.p2_suction,
                p2_discharge=row.p2_discharge,
                flow_l_min=computed.get("flow_l_min"),
                flow_m3_s=computed.get("flow_m3_s"),
                delta_pressure_psi=computed.get("delta_pressure_psi"),
                head_ft=computed.get("head_ft"),
                hydraulic_power_w=computed.get("hydraulic_power_w"),
                raw_line="manual_pressure_input",
                is_valid=True,
            )
            db.add(sample)
            persisted_samples.append(sample)

        daq_session.sample_count = len(persisted_samples)
        from datetime import timezone

        if persisted_samples:
            latest_timestamp = max(sample.timestamp for sample in persisted_samples)
            if latest_timestamp.tzinfo is None:
                latest_timestamp = latest_timestamp.replace(tzinfo=timezone.utc)
            daq_session.ended_at = latest_timestamp

        db.add(daq_session)
        db.commit()
        db.refresh(daq_session)

        for sample in persisted_samples:
            session_service._append_sample_to_csv(csv_path, sample)

        return daq_session


@router.post("/stop", response_model=StopSessionResponse)
def stop_session():
    try:
        return session_service.stop_session()
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/active", response_model=DAQSessionRead | ApiMessage)
def active_session():
    current = session_service.get_active_session()
    if not current:
        return ApiMessage(message="No active recording session.")
    return current


@router.get("", response_model=list[DAQSessionRead])
def list_sessions(limit: int = 100):
    return session_service.list_sessions(limit=limit)


@router.post("/compare", response_model=CompareSessionsResponse)
def compare_sessions(request: CompareSessionsRequest):
    summaries = session_service.compare_sessions(request.session_ids)
    if not summaries:
        raise HTTPException(status_code=404, detail="No matching sessions found.")
    return CompareSessionsResponse(summaries=summaries)


@router.get("/{session_id}", response_model=DAQSessionRead)
def get_session(session_id: int):
    daq_session = session_service.get_session(session_id)
    if not daq_session:
        raise HTTPException(status_code=404, detail="Session not found.")
    return daq_session


@router.get("/{session_id}/samples", response_model=list[SensorSampleRead])
def get_session_samples(session_id: int, limit: int = 2000):
    if not session_service.get_session(session_id):
        raise HTTPException(status_code=404, detail="Session not found.")
    return session_service.get_samples(session_id=session_id, limit=limit)


@router.get("/{session_id}/summary")
def get_session_summary(session_id: int):
    summary = session_service.summarize_session(session_id)
    if not summary:
        raise HTTPException(status_code=404, detail="Session not found.")
    return summary


@router.get("/{session_id}/export")
def export_session_csv_frontend_alias(session_id: int):
    # Alias used by the Streamlit frontend.
    return _export_session_file(session_id)


@router.get("/{session_id}/export.csv")
def export_session_csv(session_id: int):
    return _export_session_file(session_id)
