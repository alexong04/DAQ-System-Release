import csv
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, List, Optional

from sqlmodel import Session, col, func, select

from app.config import get_settings
from app.database import engine
from app.models import DAQSession, SensorSample
from app.schemas import SessionSummary

CSV_HEADERS = [
    "timestamp",
    "pump_mode",
    "timer",
    "flow_l_hr",
    "p1_suction",
    "p1_discharge",
    "p2_suction",
    "p2_discharge",
    "flow_l_min",
    "head_ft",
]


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class SessionService:
    """Owns the current recording session and handles sample persistence."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._active_session_id: Optional[int] = None
        self.settings = get_settings()

    @property
    def active_session_id(self) -> Optional[int]:
        with self._lock:
            return self._active_session_id

    def start_session(self, name: str, pump_mode: str, notes: Optional[str] = None) -> DAQSession:
        with self._lock:
            if self._active_session_id is not None:
                raise RuntimeError("A session is already recording. Stop it first before starting a new one.")

            with Session(engine) as db:
                daq_session = DAQSession(name=name, pump_mode=pump_mode, notes=notes)
                db.add(daq_session)
                db.commit()
                db.refresh(daq_session)

                csv_path = self.settings.sessions_dir / f"session_{daq_session.id:04d}.csv"
                self._initialize_csv(csv_path)
                daq_session.csv_path = str(csv_path)
                db.add(daq_session)
                db.commit()
                db.refresh(daq_session)

                self._active_session_id = daq_session.id
                return daq_session

    def stop_session(self) -> DAQSession:
        with self._lock:
            if self._active_session_id is None:
                raise RuntimeError("No active session is currently recording.")

            with Session(engine) as db:
                daq_session = db.get(DAQSession, self._active_session_id)
                if not daq_session:
                    self._active_session_id = None
                    raise RuntimeError("Active session was not found in the database.")

                daq_session.ended_at = _utc_now()
                db.add(daq_session)
                db.commit()
                db.refresh(daq_session)
                self._active_session_id = None
                return daq_session

    def get_active_session(self) -> Optional[DAQSession]:
        session_id = self.active_session_id
        if session_id is None:
            return None
        with Session(engine) as db:
            return db.get(DAQSession, session_id)

    def record_sample(self, sample: SensorSample) -> SensorSample:
        session_id = self.active_session_id
        if session_id is None:
            return sample

        with Session(engine) as db:
            daq_session = db.get(DAQSession, session_id)
            if not daq_session or daq_session.ended_at is not None:
                return sample

            sample.session_id = session_id
            sample.pump_mode = daq_session.pump_mode
            db.add(sample)
            daq_session.sample_count += 1
            db.add(daq_session)
            db.commit()
            db.refresh(sample)

            if daq_session.csv_path:
                self._append_sample_to_csv(Path(daq_session.csv_path), sample)

            return sample

    def list_sessions(self, limit: int = 100) -> List[DAQSession]:
        with Session(engine) as db:
            statement = select(DAQSession).order_by(col(DAQSession.started_at).desc()).limit(limit)
            return list(db.exec(statement).all())

    def get_session(self, session_id: int) -> Optional[DAQSession]:
        with Session(engine) as db:
            return db.get(DAQSession, session_id)

    def get_samples(self, session_id: int, limit: int = 2000) -> List[SensorSample]:
        with Session(engine) as db:
            statement = (
                select(SensorSample)
                .where(SensorSample.session_id == session_id)
                .order_by(SensorSample.timestamp)
                .limit(limit)
            )
            return list(db.exec(statement).all())

    def get_csv_path(self, session_id: int) -> Optional[Path]:
        daq_session = self.get_session(session_id)
        if not daq_session or not daq_session.csv_path:
            return None
        path = Path(daq_session.csv_path)
        return path if path.exists() else None

    def summarize_session(self, session_id: int) -> Optional[SessionSummary]:
        with Session(engine) as db:
            daq_session = db.get(DAQSession, session_id)
            if not daq_session:
                return None

            statement = select(
                func.avg(SensorSample.flow_l_hr),
                func.max(SensorSample.flow_l_hr),
                func.avg(SensorSample.head_ft),
                func.max(SensorSample.head_ft),
                func.avg(SensorSample.delta_pressure_psi),
                func.max(SensorSample.delta_pressure_psi),
                func.avg(SensorSample.hydraulic_power_w),
                func.max(SensorSample.hydraulic_power_w),
            ).where(SensorSample.session_id == session_id)

            row = db.exec(statement).one()

            return SessionSummary(
                session_id=daq_session.id,
                name=daq_session.name,
                pump_mode=daq_session.pump_mode,
                sample_count=daq_session.sample_count,
                started_at=daq_session.started_at,
                ended_at=daq_session.ended_at,
                avg_flow_l_hr=self._float_or_none(row[0]),
                max_flow_l_hr=self._float_or_none(row[1]),
                avg_head_ft=self._float_or_none(row[2]),
                max_head_ft=self._float_or_none(row[3]),
                avg_delta_pressure_psi=self._float_or_none(row[4]),
                max_delta_pressure_psi=self._float_or_none(row[5]),
                avg_hydraulic_power_w=self._float_or_none(row[6]),
                max_hydraulic_power_w=self._float_or_none(row[7]),
            )

    def compare_sessions(self, session_ids: Iterable[int]) -> List[SessionSummary]:
        summaries = []
        for session_id in session_ids:
            summary = self.summarize_session(session_id)
            if summary:
                summaries.append(summary)
        return summaries

    @staticmethod
    def _float_or_none(value) -> Optional[float]:
        return None if value is None else float(value)

    @staticmethod
    def _initialize_csv(path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", newline="", encoding="utf-8") as file:
            writer = csv.DictWriter(file, fieldnames=CSV_HEADERS)
            writer.writeheader()

    @staticmethod
    def _append_sample_to_csv(path: Path, sample: SensorSample) -> None:
        with path.open("a", newline="", encoding="utf-8") as file:
            writer = csv.DictWriter(file, fieldnames=CSV_HEADERS)
            writer.writerow(
                {
                    "timestamp": sample.timestamp.isoformat(),
                    "pump_mode": sample.pump_mode,
                    "timer": sample.timer,
                    "flow_l_hr": sample.flow_l_hr,
                    "p1_suction": sample.p1_suction,
                    "p1_discharge": sample.p1_discharge,
                    "p2_suction": sample.p2_suction,
                    "p2_discharge": sample.p2_discharge,
                    "flow_l_min": sample.flow_l_min,
                    "head_ft": sample.head_ft,
                }
            )


session_service = SessionService()
