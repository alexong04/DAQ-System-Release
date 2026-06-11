from __future__ import annotations

from typing import Any

import requests


class BackendError(Exception):
    pass


class ApiClient:
    def __init__(self, base_url: str, timeout: tuple[float, float] = (0.25, 0.5)):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def _url(self, path: str) -> str:
        return f"{self.base_url}{path}"

    def _request(self, method: str, path: str, **kwargs) -> Any:
        timeout = kwargs.pop("timeout", self.timeout)
        try:
            response = requests.request(
                method=method,
                url=self._url(path),
                timeout=timeout,
                **kwargs,
            )
        except requests.RequestException as exc:
            raise BackendError(f"Cannot connect to backend at {self.base_url}") from exc

        if not response.ok:
            message = f"Backend request failed: {response.status_code}"

            try:
                body = response.json()
                message = body.get("detail") or body.get("message") or message
            except ValueError:
                if response.text:
                    message = response.text[:240]

            raise BackendError(message)

        if response.status_code == 204:
            return None

        try:
            return response.json()
        except ValueError as exc:
            raise BackendError("Backend returned non-JSON response.") from exc

    def health(self) -> dict:
        return self._request("GET", "/api/health")

    def get_recent_samples(self, limit: int = 300) -> list[dict]:
        data = self._request("GET", f"/api/live/recent?limit={limit}")
        if isinstance(data, list):
            return data
        return data.get("items", [])


    def get_serial_ports(self) -> list[dict]:
        data = self._request("GET", "/api/serial/ports")
        if isinstance(data, list):
            return data
        return data.get("items", [])

    def get_serial_status(self) -> dict:
        return self._request("GET", "/api/serial/status")

    def connect_serial(self, port: str, baud_rate: int = 9600) -> dict:
        return self._request(
            "POST",
            "/api/serial/connect",
            json={"port": port, "baud_rate": baud_rate},
            timeout=(1.0, 6.0),
        )

    def auto_connect_serial(self, baud_rate: int = 9600, probe_seconds: float = 3.0) -> dict:
        return self._request(
            "POST",
            "/api/serial/auto-connect",
            json={"baud_rate": baud_rate, "probe_seconds": probe_seconds},
            timeout=(1.0, 20.0),
        )

    def disconnect_serial(self) -> dict:
        return self._request("POST", "/api/serial/disconnect", timeout=(1.0, 6.0))

    def start_session(self, name: str, pump_mode: str) -> dict:
        return self._request(
            "POST",
            "/api/sessions/start",
            json={"name": name, "pump_mode": pump_mode},
        )

    def stop_session(self) -> dict | None:
        return self._request("POST", "/api/sessions/stop")

    def get_sessions(self) -> list[dict]:
        data = self._request("GET", "/api/sessions")
        if isinstance(data, list):
            return data
        return data.get("items", [])

    def get_session_samples(self, session_id: str) -> list[dict]:
        data = self._request("GET", f"/api/sessions/{session_id}/samples")
        if isinstance(data, list):
            return data
        return data.get("items", [])

    def export_url(self, session_id: str) -> str:
        return self._url(f"/api/sessions/{session_id}/export")
