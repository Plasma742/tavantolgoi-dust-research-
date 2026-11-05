"""Typed API errors. Every error body is ``{"error": {"code", "message", "details"}}``."""

from __future__ import annotations

from typing import Any


class ApiError(Exception):
    status_code = 400
    code = "BAD_REQUEST"

    def __init__(
        self, message: str, *, details: Any | None = None, code: str | None = None, status_code: int | None = None
    ):
        super().__init__(message)
        self.message = message
        self.details = details
        if code:
            self.code = code
        if status_code:
            self.status_code = status_code

    def body(self) -> dict[str, Any]:
        return {"error": {"code": self.code, "message": self.message, "details": self.details}}


class InvalidRoi(ApiError):
    status_code = 400
    code = "INVALID_ROI"


class InvalidPeriod(ApiError):
    status_code = 400
    code = "INVALID_PERIOD"


class NotConfigured(ApiError):
    status_code = 503
    code = "NOT_CONFIGURED"


class EarthEngineUnavailable(ApiError):
    status_code = 503
    code = "EE_UNAVAILABLE"


class NotImplementedDataset(ApiError):
    status_code = 501
    code = "NOT_IMPLEMENTED"


class UnknownDataset(ApiError):
    status_code = 404
    code = "UNKNOWN_DATASET"


class TileExpired(ApiError):
    status_code = 410  # Gone: MapLibre surfaces 410 as an error event, but ignores 404 tiles
    code = "TILE_EXPIRED"


def classify_ee_error(exc: Exception) -> ApiError:
    """Map an Earth Engine exception to a stable API error without leaking credentials."""
    text = str(exc)[:600]
    lowered = text.lower()
    if "timed out" in lowered or "deadline" in lowered:
        return ApiError(
            "Earth Engine computation timed out. Reduce the ROI or date range.",
            code="EE_TIMEOUT",
            status_code=504,
            details=text,
        )
    if "quota" in lowered or "too many" in lowered or "rate limit" in lowered:
        return ApiError(
            "Earth Engine quota or concurrency limit reached. Retry later.",
            code="EE_QUOTA",
            status_code=429,
            details=text,
        )
    if "permission" in lowered or "not registered" in lowered or "403" in lowered:
        return ApiError(
            "Earth Engine denied access for the configured Cloud project.",
            code="EE_PERMISSION",
            status_code=502,
            details=text,
        )
    return ApiError("Earth Engine returned an error.", code="EE_ERROR", status_code=502, details=text)
