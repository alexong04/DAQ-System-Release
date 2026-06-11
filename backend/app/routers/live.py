from fastapi import APIRouter, Query

from app.schemas import SensorSampleRead
from app.services.serial_service import serial_service

router = APIRouter(prefix="/live", tags=["live"])


@router.get("/recent", response_model=list[SensorSampleRead])
def recent_live_samples(limit: int = Query(default=300, ge=1, le=5000)):
    """Return the latest in-memory samples for the Streamlit dashboard."""
    return serial_service.recent_samples(limit=limit)
