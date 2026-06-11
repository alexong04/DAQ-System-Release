import asyncio
import math
import random
import threading
from collections import deque
import time
from datetime import datetime, timezone
from typing import Optional

from app.calculations import compute_engineering_values
from app.models import SensorSample
from app.schemas import SerialStatus
from app.sensor_parser import parse_sensor_line
from app.services.session_service import session_service
from app.services.websocket_manager import websocket_manager


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class SerialService:
    """Reads Arduino/HC-05 serial data and broadcasts live samples."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._serial = None
        self._thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._event_loop: Optional[asyncio.AbstractEventLoop] = None

        self.connected = False
        self.port: Optional[str] = None
        self.baud_rate: Optional[int] = None
        self.mode: str = "idle"  # idle | serial | simulator
        self.last_line: Optional[str] = None
        self.last_error: Optional[str] = None
        self.samples_received = 0
        self.latest_sample: Optional[SensorSample] = None
        self._recent_samples = deque(maxlen=5000)

    def bind_event_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        self._event_loop = loop

    def status(self) -> SerialStatus:
        with self._lock:
            return SerialStatus(
                connected=self.connected,
                port=self.port,
                baud_rate=self.baud_rate,
                mode=self.mode,
                last_line=self.last_line,
                last_error=self.last_error,
                samples_received=self.samples_received,
            )

    def latest(self) -> Optional[SensorSample]:
        with self._lock:
            return self.latest_sample

    def recent_samples(self, limit: int = 300):
        with self._lock:
            safe_limit = max(1, min(int(limit or 300), self._recent_samples.maxlen or 5000))
            return list(self._recent_samples)[-safe_limit:]

    def connect(self, port: str, baud_rate: int) -> SerialStatus:
        with self._lock:
            if self.connected:
                raise RuntimeError("Serial service is already connected. Disconnect first.")

            self._stop_event.clear()
            self.port = port
            self.baud_rate = baud_rate
            self.last_error = None
            self.samples_received = 0
            self._recent_samples.clear()

            if port.upper() == "SIMULATOR":
                self.mode = "simulator"
                self.connected = True
                self._thread = threading.Thread(target=self._simulator_loop, daemon=True)
                self._thread.start()
                return self.status()

            try:
                import serial

                self._serial = serial.Serial(port=port, baudrate=baud_rate, timeout=1)
                # Some Arduino boards reset after opening serial; give it a moment.
                time.sleep(2)
            except Exception as exc:
                self._serial = None
                self.connected = False
                self.mode = "idle"
                self.last_error = str(exc)
                raise RuntimeError(f"Failed to open serial port {port}: {exc}") from exc

            self.mode = "serial"
            self.connected = True
            self._thread = threading.Thread(target=self._read_loop, daemon=True)
            self._thread.start()
            return self.status()

    def disconnect(self) -> SerialStatus:
        with self._lock:
            self._stop_event.set()

        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=3)

        with self._lock:
            if self._serial is not None:
                try:
                    self._serial.close()
                except Exception as exc:
                    self.last_error = str(exc)
                finally:
                    self._serial = None

            self.connected = False
            self.mode = "idle"
            self._thread = None
            return self.status()

    def list_ports(self):
        try:
            from serial.tools import list_ports

            return [
                {
                    "device": port.device,
                    "description": port.description,
                    "hwid": port.hwid,
                }
                for port in list_ports.comports()
            ]
        except Exception as exc:
            self.last_error = str(exc)
            return []

    @staticmethod
    def _port_score(port_info: dict, hints: Optional[list[str]] = None) -> tuple[int, str]:
        device = str(port_info.get("device") or "")
        description = str(port_info.get("description") or "")
        hwid = str(port_info.get("hwid") or "")
        haystack = f"{device} {description} {hwid}".lower()

        keywords = [
            "hc-05",
            "hc05",
            "bluetooth",
            "standard serial over bluetooth",
            "serial over bluetooth",
            "bt",
            "arduino",
            "usb serial",
            "usb-serial",
            "ch340",
            "cp210",
        ]

        score = 0
        for hint in hints or []:
            hint_text = str(hint).strip().lower()
            if hint_text and hint_text in haystack:
                score += 100

        for index, keyword in enumerate(keywords):
            if keyword in haystack:
                score += 50 - index

        return (-score, device)

    def _auto_connect_candidates(self, hints: Optional[list[str]] = None) -> list[str]:
        ports = self.list_ports()
        ordered = sorted(ports, key=lambda item: self._port_score(item, hints))
        seen = set()
        candidates = []
        for item in ordered:
            device = str(item.get("device") or "").strip()
            if device and device not in seen:
                seen.add(device)
                candidates.append(device)
        return candidates

    def auto_connect(
        self,
        baud_rate: int,
        probe_seconds: float = 3.0,
        port_hints: Optional[list[str]] = None,
    ) -> SerialStatus:
        """Try likely HC-05/Bluetooth ports and keep the first one that produces a line."""
        if self.connected:
            raise RuntimeError("Serial service is already connected. Disconnect first before auto-detecting.")

        candidates = self._auto_connect_candidates(port_hints)
        if not candidates:
            raise RuntimeError("No serial/COM ports were detected. Pair the HC-05 first, then refresh ports.")

        errors = []
        probe_seconds = max(0.5, min(float(probe_seconds or 3.0), 10.0))

        for port in candidates:
            try:
                status = self.connect(port, baud_rate)
            except RuntimeError as exc:
                errors.append(f"{port}: {exc}")
                continue

            deadline = time.time() + probe_seconds
            while time.time() < deadline:
                current = self.status()
                if current.samples_received > 0 or current.last_line:
                    return current
                time.sleep(0.2)

            errors.append(f"{port}: opened but no data was received within {probe_seconds:g}s")
            self.disconnect()

        self.last_error = "Auto-connect failed. " + " | ".join(errors[-5:])
        raise RuntimeError(self.last_error)

    def _read_loop(self) -> None:
        while not self._stop_event.is_set():
            try:
                if self._serial is None:
                    break
                raw = self._serial.readline()
                if not raw:
                    continue
                line = raw.decode("utf-8", errors="replace").strip()
                if line:
                    self._handle_line(line)
            except Exception as exc:
                with self._lock:
                    self.last_error = str(exc)
                time.sleep(0.5)

    def _simulator_loop(self) -> None:
        start = time.time()
        while not self._stop_event.is_set():
            elapsed = time.time() - start

            # Simulated test-rig behavior using the same CSV order as Arduino:
            # timer,flow_l_hr,p1_suction,p1_discharge,p2_suction,p2_discharge
            flow_l_hr = 290 + 35 * math.sin(elapsed / 9) + random.uniform(-4, 4)
            p1_suction = 8.0 + 0.5 * math.sin(elapsed / 11) + random.uniform(-0.08, 0.08)
            p1_discharge = p1_suction + 4.5 + 0.4 * math.sin(elapsed / 7) + random.uniform(-0.08, 0.08)
            p2_suction = p1_discharge + 0.6 + random.uniform(-0.05, 0.05)
            p2_discharge = p2_suction + 3.8 + 0.3 * math.sin(elapsed / 6) + random.uniform(-0.08, 0.08)

            line = (
                f"{elapsed:.0f},{flow_l_hr:.3f},{p1_suction:.3f},{p1_discharge:.3f},"
                f"{p2_suction:.3f},{p2_discharge:.3f}"
            )
            self._handle_line(line)
            time.sleep(1)

    def _handle_line(self, line: str) -> None:
        active_session = session_service.get_active_session()
        pump_mode = active_session.pump_mode if active_session else "series"

        parsed = parse_sensor_line(line)
        values = parsed.values
        computed = compute_engineering_values(pump_mode, values)

        sample = SensorSample(
            timestamp=_utc_now(),
            pump_mode=pump_mode,
            timer=values.get("timer"),
            flow_l_hr=values.get("flow_l_hr"),
            p1_suction=values.get("p1_suction"),
            p1_discharge=values.get("p1_discharge"),
            p2_suction=values.get("p2_suction"),
            p2_discharge=values.get("p2_discharge"),
            flow_l_min=computed.get("flow_l_min"),
            flow_m3_s=computed.get("flow_m3_s"),
            delta_pressure_psi=computed.get("delta_pressure_psi"),
            head_ft=computed.get("head_ft"),
            hydraulic_power_w=computed.get("hydraulic_power_w"),
            raw_line=line,
            is_valid=parsed.is_valid,
            parse_error=parsed.error,
        )

        saved_sample = session_service.record_sample(sample)

        with self._lock:
            self.last_line = line
            self.latest_sample = saved_sample
            self._recent_samples.append(saved_sample)
            self.samples_received += 1
            if parsed.error:
                self.last_error = parsed.error

        self._broadcast_sample(saved_sample)

    def _broadcast_sample(self, sample: SensorSample) -> None:
        if self._event_loop is None or self._event_loop.is_closed():
            return

        payload = {
            "type": "sample",
            "data": {
                "id": sample.id,
                "session_id": sample.session_id,
                "timestamp": sample.timestamp.isoformat(),
                "pump_mode": sample.pump_mode,
                "timer": sample.timer,
                "flow_l_hr": sample.flow_l_hr,
                "p1_suction": sample.p1_suction,
                "p1_discharge": sample.p1_discharge,
                "p2_suction": sample.p2_suction,
                "p2_discharge": sample.p2_discharge,
                "flow_l_min": sample.flow_l_min,
                "flow_m3_s": sample.flow_m3_s,
                "delta_pressure_psi": sample.delta_pressure_psi,
                "head_ft": sample.head_ft,
                "hydraulic_power_w": sample.hydraulic_power_w,
                "raw_line": sample.raw_line,
                "is_valid": sample.is_valid,
                "parse_error": sample.parse_error,
            },
        }
        asyncio.run_coroutine_threadsafe(websocket_manager.broadcast_json(payload), self._event_loop)


serial_service = SerialService()
