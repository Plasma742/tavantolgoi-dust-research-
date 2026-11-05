"""Runtime configuration from environment variables (see ../.env.example).

No secret values are read here. Earth Engine credentials are resolved by Google's
libraries (Application Default Credentials or ``earthengine authenticate``), never
from this repository.
"""

from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def _env(name: str, default: str | None = None) -> str | None:
    value = os.environ.get(name)
    if value is None or value.strip() == "":
        return default
    return value.strip()


def _env_int(name: str, default: int) -> int:
    raw = _env(name)
    return int(raw) if raw is not None else default


def _env_float(name: str, default: float) -> float:
    raw = _env(name)
    return float(raw) if raw is not None else default


def _bbox(raw: str | None, default: tuple[float, float, float, float]) -> tuple[float, float, float, float]:
    if raw is None:
        return default
    parts = [float(p) for p in raw.split(",")]
    if len(parts) != 4:
        raise ValueError("ALLOWED_BBOX must be 'west,south,east,north'")
    west, south, east, north = parts
    if not (-180 <= west < east <= 180 and -90 <= south < north <= 90):
        raise ValueError("ALLOWED_BBOX is not a valid lon/lat box")
    return west, south, east, north


def _git_revision() -> str | None:
    try:
        out = subprocess.run(
            ["git", "-C", str(REPO_ROOT), "rev-parse", "--short=12", "HEAD"],
            capture_output=True,
            text=True,
            timeout=2,
            check=True,
        )
        rev = out.stdout.strip()
        dirty = subprocess.run(
            ["git", "-C", str(REPO_ROOT), "status", "--porcelain"],
            capture_output=True,
            text=True,
            timeout=2,
            check=True,
        ).stdout.strip()
        return f"{rev}{'-dirty' if dirty else ''}" if rev else None
    except (OSError, subprocess.SubprocessError):
        return None


@dataclass(frozen=True)
class Settings:
    ee_project_id: str | None
    ee_auth_mode: str  # "persistent" (local `earthengine authenticate`) or "adc"
    allowed_origins: tuple[str, ...]
    max_roi_area_km2: float
    max_roi_vertices: int
    allowed_bbox: tuple[float, float, float, float]
    max_layer_days: int
    max_series_months: int
    ee_max_parallel: int
    ee_max_pixels: int
    layer_cache_ttl_s: int
    stats_cache_ttl_s: int
    max_request_bytes: int
    roi_dir: Path
    code_revision: str | None
    app_mode: str = "local"  # "local" | "public"
    auth_provider: str = "none"  # "none" | "iap"
    iap_audience: str | None = None
    authorized_principals: tuple[str, ...] = ()
    rate_limit_compute_per_min: int = 30
    rate_limit_tiles_per_min: int = 1200
    max_concurrent_compute: int = 4
    compute_queue_timeout_s: float = 15.0
    tile_max_zoom: int = 13

    @property
    def ee_configured(self) -> bool:
        return bool(self.ee_project_id)

    @property
    def public(self) -> bool:
        return self.app_mode == "public"

    def validate_for_startup(self) -> None:
        """Refuse unsafe public configurations instead of running them."""
        if self.app_mode not in {"local", "public"}:
            raise ValueError("APP_MODE must be 'local' or 'public'")
        if self.auth_provider not in {"none", "iap"}:
            raise ValueError("AUTH_PROVIDER must be 'none' or 'iap'")
        if self.public:
            if self.auth_provider == "none":
                raise ValueError("APP_MODE=public requires AUTH_PROVIDER (e.g. iap); refusing to start.")
            if self.auth_provider == "iap" and not self.iap_audience:
                raise ValueError("AUTH_PROVIDER=iap requires IAP_AUDIENCE.")
            if "*" in self.allowed_origins:
                raise ValueError("ALLOWED_ORIGINS must list explicit origins in public mode (no '*').")


def load_settings() -> Settings:
    origins = _env("ALLOWED_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173") or ""
    auth_mode = (_env("EE_AUTH_MODE", "persistent") or "persistent").lower()
    if auth_mode not in {"persistent", "adc"}:
        raise ValueError("EE_AUTH_MODE must be 'persistent' or 'adc'")
    roi_dir = Path(_env("ROI_DIR", str(REPO_ROOT / "data" / "roi")) or "")
    if not roi_dir.is_absolute():
        roi_dir = (REPO_ROOT / roi_dir).resolve()
    return Settings(
        ee_project_id=_env("EE_PROJECT_ID"),
        ee_auth_mode=auth_mode,
        allowed_origins=tuple(o.strip() for o in origins.split(",") if o.strip()),
        max_roi_area_km2=_env_float("MAX_ROI_AREA_KM2", 10_000.0),
        max_roi_vertices=_env_int("MAX_ROI_VERTICES", 2_000),
        # Default: a box around Mongolia. Requests outside it are rejected to protect quota.
        allowed_bbox=_bbox(_env("ALLOWED_BBOX"), (87.0, 41.0, 120.0, 52.5)),
        max_layer_days=_env_int("MAX_LAYER_DAYS", 31),
        max_series_months=_env_int("MAX_SERIES_MONTHS", 36),
        ee_max_parallel=max(1, _env_int("EE_MAX_PARALLEL", 3)),
        ee_max_pixels=_env_int("EE_MAX_PIXELS", 10_000_000),
        layer_cache_ttl_s=_env_int("LAYER_CACHE_TTL_S", 3_600),
        stats_cache_ttl_s=_env_int("STATS_CACHE_TTL_S", 86_400),
        max_request_bytes=_env_int("MAX_REQUEST_BYTES", 1_000_000),
        roi_dir=roi_dir,
        code_revision=_env("CODE_REVISION") or _git_revision(),
        app_mode=(_env("APP_MODE", "local") or "local").lower(),
        auth_provider=(_env("AUTH_PROVIDER", "none") or "none").lower(),
        iap_audience=_env("IAP_AUDIENCE"),
        authorized_principals=tuple(
            p.strip().lower() for p in (_env("AUTHORIZED_PRINCIPALS", "") or "").split(",") if p.strip()
        ),
        rate_limit_compute_per_min=_env_int("RATE_LIMIT_COMPUTE_PER_MIN", 30),
        rate_limit_tiles_per_min=_env_int("RATE_LIMIT_TILES_PER_MIN", 1200),
        max_concurrent_compute=_env_int("MAX_CONCURRENT_COMPUTE", 4),
        compute_queue_timeout_s=_env_float("COMPUTE_QUEUE_TIMEOUT_S", 15.0),
    )
