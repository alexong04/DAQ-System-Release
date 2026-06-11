from fastapi import APIRouter, HTTPException

from app.config import get_settings
from app.schemas import ApiMessage, PortInfo, SerialAutoConnectRequest, SerialConnectRequest, SerialStatus, SensorSampleRead
from app.services.serial_service import serial_service

router = APIRouter(prefix="/serial", tags=["serial"])
settings = get_settings()


@router.get("/ports", response_model=list[PortInfo])
def list_ports():
    return serial_service.list_ports()


@router.post("/connect", response_model=SerialStatus)
def connect_serial(request: SerialConnectRequest):
    try:
        return serial_service.connect(request.port, request.baud_rate or settings.default_baud_rate)
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/auto-connect", response_model=SerialStatus)
def auto_connect_serial(request: SerialAutoConnectRequest):
    try:
        return serial_service.auto_connect(
            baud_rate=request.baud_rate or settings.default_baud_rate,
            probe_seconds=request.probe_seconds,
            port_hints=request.port_hints,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/disconnect", response_model=SerialStatus)
def disconnect_serial():
    return serial_service.disconnect()


@router.get("/status", response_model=SerialStatus)
def serial_status():
    return serial_service.status()


@router.get("/latest", response_model=SensorSampleRead | ApiMessage)
def latest_sample():
    if serial_service.latest_sample is None:
        return ApiMessage(message="No sensor sample has been received yet.")
    return serial_service.latest_sample
