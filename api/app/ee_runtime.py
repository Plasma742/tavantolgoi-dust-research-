"""Earth Engine session management. Credentials never leave the server.

Status values reported by ``/api/health``:

* ``NOT_CONFIGURED`` — ``EE_PROJECT_ID`` is not set. No Earth Engine call is attempted.
* ``NOT_INITIALIZED`` — configured, not yet contacted.
* ``READY``           — ``ee.Initialize`` succeeded.
* ``AUTH_ERROR``      — initialisation failed (no credentials, project not registered, ...).
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Any

from .config import Settings
from .errors import EarthEngineUnavailable, NotConfigured

log = logging.getLogger(__name__)

EE_SCOPES = (
    "https://www.googleapis.com/auth/earthengine",
    "https://www.googleapis.com/auth/cloud-platform",
)
RETRY_AFTER_FAILURE_S = 60


class EERuntime:
    def __init__(self, settings: Settings):
        self._settings = settings
        self._lock = threading.Lock()
        self._status = "NOT_CONFIGURED" if not settings.ee_configured else "NOT_INITIALIZED"
        self._message: str | None = None
        self._last_attempt = 0.0
        self._ee_version: str | None = None

    def snapshot(self) -> dict[str, Any]:
        return {
            "status": self._status,
            "message": self._message,
            "project_configured": self._settings.ee_configured,
            "auth_mode": self._settings.ee_auth_mode,
            "earthengine_api_version": self._ee_version,
        }

    @property
    def earthengine_api_version(self) -> str | None:
        return self._ee_version

    def ensure_ready(self) -> None:
        """Initialise Earth Engine once; raise a typed API error if that is impossible."""
        if not self._settings.ee_configured:
            raise NotConfigured(
                "Earth Engine is NOT_CONFIGURED: set EE_PROJECT_ID (and authenticate) on the "
                "backend. No observations can be served until then.",
            )
        if self._status == "READY":
            return
        with self._lock:
            if self._status == "READY":
                return
            if self._status == "AUTH_ERROR" and time.monotonic() - self._last_attempt < RETRY_AFTER_FAILURE_S:
                raise EarthEngineUnavailable(f"Earth Engine initialisation failed: {self._message}")
            self._last_attempt = time.monotonic()
            try:
                import ee  # imported lazily so NOT_CONFIGURED deployments never touch it

                self._ee_version = getattr(ee, "__version__", None)
                if self._settings.ee_auth_mode == "adc":
                    import google.auth

                    credentials, _ = google.auth.default(scopes=list(EE_SCOPES))
                    ee.Initialize(credentials=credentials, project=self._settings.ee_project_id)
                else:
                    ee.Initialize(project=self._settings.ee_project_id)
                self._status, self._message = "READY", None
                log.info("Earth Engine initialised (auth mode %s)", self._settings.ee_auth_mode)
            except Exception as exc:  # broad on purpose: report, never crash the API
                self._status = "AUTH_ERROR"
                self._message = f"{type(exc).__name__}: {str(exc)[:300]}"
                log.warning("Earth Engine initialisation failed: %s", self._message)
                raise EarthEngineUnavailable(f"Earth Engine initialisation failed: {self._message}") from exc
