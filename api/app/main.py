"""FastAPI application: Tavan Tolgoi Dust Research Platform API.

Run locally (from api/):  uvicorn app.main:app --host 127.0.0.1 --port 8000 --env-file .env

Default APP_MODE=local is for one researcher on 127.0.0.1 and is NOT a public deployment.
APP_MODE=public enables authentication, authorisation and stricter disclosure; see
docs/DEPLOYMENT_CHECKLIST.md before ever using it.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

from fastapi import Depends, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse, Response

from . import __version__
from .config import Settings, load_settings
from .csv_export import monthly_csv
from .datasets import maiac_spec
from .datasets.maiac_service import MaiacEngine, MaiacService
from .datasets.registry import DATASETS, UNAVAILABLE_MODULES, get_dataset
from .ee_runtime import EERuntime
from .errors import ApiError, NotImplementedDataset, UnknownDataset, classify_ee_error
from .roi import load_registry
from .schemas import LayerResponse, MaiacLayerRequest, MonthlySeriesRequest, MonthlySeriesResponse
from .security import (
    LOCAL_PRINCIPAL,
    Authenticator,
    BodySizeLimitMiddleware,
    ComputeLimiter,
    Forbidden,
    IapAuthenticator,
    Principal,
    RateLimiter,
    Unauthenticated,
)
from .tiles import TileRegistry

log = logging.getLogger("tavantolgoi.api")


def _default_engine_factory(settings: Settings) -> Callable[[], MaiacEngine]:
    def factory() -> MaiacEngine:
        from .datasets.maiac_ee import MaiacEarthEngine  # imports `ee`; only after init succeeded

        return MaiacEarthEngine(max_pixels=settings.ee_max_pixels)

    return factory


def create_app(
    settings: Settings | None = None,
    *,
    runtime: EERuntime | None = None,
    engine_factory: Callable[[], MaiacEngine] | None = None,
    authenticator: Authenticator | None = None,
    clock: Callable[[], float] | None = None,
) -> FastAPI:
    settings = settings or load_settings()
    settings.validate_for_startup()
    if settings.public and authenticator is None:
        authenticator = IapAuthenticator(settings.iap_audience or "")
    runtime = runtime or EERuntime(settings)
    tiles = TileRegistry(ttl_s=settings.layer_cache_ttl_s + 300, max_zoom=settings.tile_max_zoom)
    registry, registry_problems = load_registry(
        settings.roi_dir,
        max_area_km2=settings.max_roi_area_km2,
        max_vertices=settings.max_roi_vertices,
        allowed_bbox=settings.allowed_bbox,
    )
    maiac = MaiacService(settings, runtime, engine_factory or _default_engine_factory(settings), tiles, registry)
    limiter_kw = {"clock": clock} if clock else {}
    compute_rate = RateLimiter(settings.rate_limit_compute_per_min, **limiter_kw)
    tile_rate = RateLimiter(settings.rate_limit_tiles_per_min, **limiter_kw)
    compute_slots = ComputeLimiter(settings.max_concurrent_compute, settings.compute_queue_timeout_s)

    app = FastAPI(
        title="Tavan Tolgoi Dust Research Platform API",
        version=__version__,
        description="Research prototype. Serves QA-filtered MAIAC AOD (550 nm) from Google Earth Engine. "
        "AOD is column aerosol optical depth, not PM10 and not mine-attributed dust.",
        docs_url=None if settings.public else "/api/docs",
        openapi_url=None if settings.public else "/api/openapi.json",
        redoc_url=None,
    )
    # CORS only tells browsers which origins may read responses. It is NOT authentication.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.allowed_origins),
        allow_methods=["GET", "POST"],
        allow_headers=["Content-Type"],
        allow_credentials=False,
    )
    app.add_middleware(BodySizeLimitMiddleware, max_bytes=settings.max_request_bytes)

    @app.exception_handler(ApiError)
    async def api_error_handler(_: Request, exc: ApiError) -> JSONResponse:
        body = exc.body()
        if settings.public and exc.code.startswith("EE_"):
            log.warning("Earth Engine error %s: %s", exc.code, exc.details)
            body["error"]["details"] = None  # never disclose backend/project details publicly
        return JSONResponse(status_code=exc.status_code, content=body)

    @app.exception_handler(RequestValidationError)
    async def validation_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
        details = [{"loc": list(e.get("loc", [])), "msg": e.get("msg")} for e in exc.errors()]
        return JSONResponse(
            status_code=422,
            content=ApiError("Request failed validation.", code="VALIDATION_ERROR", details=details).body(),
        )

    # -- access control ------------------------------------------------------------------
    def optional_principal(request: Request) -> Principal | None:
        if not settings.public:
            return LOCAL_PRINCIPAL
        if authenticator is None:  # unreachable: create_app always sets one in public mode
            raise Unauthenticated("No authentication provider configured.")
        return authenticator.authenticate({k.lower(): v for k, v in request.headers.items()})

    def require_principal(principal: Principal | None = Depends(optional_principal)) -> Principal:
        if not settings.public:
            return LOCAL_PRINCIPAL
        if principal is None:
            raise Unauthenticated("Authentication required.")
        if settings.authorized_principals and principal.id.lower() not in settings.authorized_principals:
            raise Forbidden("This account is not authorised for this research platform.")
        return principal

    def compute_access(principal: Principal = Depends(require_principal)) -> Principal:
        compute_rate.check(principal.id)
        return principal

    def tile_access(principal: Principal = Depends(require_principal)) -> Principal:
        tile_rate.check(principal.id)
        return principal

    # -- meta ------------------------------------------------------------------------------
    @app.get("/api/health")
    def health(
        check_earth_engine: bool = False, principal: Principal | None = Depends(optional_principal)
    ) -> dict[str, Any]:
        """Service status. Public mode discloses diagnostics only to authorised principals."""
        if settings.public:
            authorised = principal is not None and (
                not settings.authorized_principals or principal.id.lower() in settings.authorized_principals
            )
            if not authorised:
                return {"status": "ok"}
        if check_earth_engine and settings.ee_configured:
            try:
                runtime.ensure_ready()
            except ApiError:
                pass  # reported in the snapshot below
        return {
            "status": "ok",
            "version": __version__,
            "method_version": maiac_spec.METHOD_VERSION,
            "code_revision": settings.code_revision,
            "app_mode": settings.app_mode,
            "earth_engine": runtime.snapshot(),
            "limits": {
                "max_roi_area_km2": settings.max_roi_area_km2,
                "max_roi_vertices": settings.max_roi_vertices,
                "allowed_bbox": list(settings.allowed_bbox),
                "max_layer_days": settings.max_layer_days,
                "max_series_months": settings.max_series_months,
            },
            "deployment": "local research prototype - not publicly deployed"
            if not settings.public
            else "public mode (authenticated)",
        }

    @app.get("/api/datasets")
    def datasets(_: Principal = Depends(require_principal)) -> dict[str, Any]:
        return {"datasets": list(DATASETS.values()), "unavailable_modules": UNAVAILABLE_MODULES}

    @app.get("/api/methods")
    def methods(_: Principal = Depends(require_principal)) -> dict[str, Any]:
        return {
            "method_version": maiac_spec.METHOD_VERSION,
            "code_revision": settings.code_revision,
            "maiac": {
                "dataset_id": maiac_spec.COLLECTION_ID,
                "band": maiac_spec.AOD_BAND,
                "qa_band": maiac_spec.QA_BAND,
                "scale_factor": maiac_spec.SCALE_FACTOR,
                "unit": maiac_spec.UNIT,
                "quality_filter": maiac_spec.QA_RULE_TEXT,
                "physical_range": [maiac_spec.PRIMARY.aod_min, maiac_spec.PRIMARY.aod_max],
                "temporal_aggregation": maiac_spec.TEMPORAL_AGGREGATION_TEXT,
                "spatial_reduction": maiac_spec.SPATIAL_REDUCTION_TEXT,
                "not_a_measurement_of": list(maiac_spec.NOT_A_MEASUREMENT_OF),
                "caveat": maiac_spec.CAVEAT,
                "citation": maiac_spec.CITATION,
                "catalog_url": maiac_spec.CATALOG_URL,
                "method": maiac_spec.method_summary(),
                "parity_scripts": {
                    "acceptance": "gee/maiac_parity_check.js (mirrors the backend; generated method block)",
                    "legacy_exploratory": "gee/maiac_smoke_test.js - legacy exploratory script "
                    "(different grid/weighting and range; not an acceptance check)",
                },
                "review_notes": [
                    "Primary variant keeps small negative AOD (product valid range -0.1..8.0); the non-negative "
                    "screen is a separate sensitivity variant.",
                    "Adjacency (bits 5-7) is decoded; filtering on it is a sensitivity variant, not the primary.",
                    "Undocumented or reserved AOD_QA values are rejected and counted (qa_guard_rejections).",
                    "Parity with the Code Editor has not yet been demonstrated on live Earth Engine.",
                ],
            },
            "quota_note": "Earth Engine noncommercial projects have monthly EECU-hour quotas (since 27 April 2026). "
            "The backend bounds ROI size, period length and series length, limits request rate and "
            "concurrency, and caches results.",
        }

    @app.get("/api/rois")
    def rois(_: Principal = Depends(require_principal)) -> dict[str, Any]:
        return {
            "rois": [entry.public() for entry in registry.values()],
            "problems": registry_problems,
            "note": "Only server-registered ROIs are listed. Drawn or uploaded ROIs are labelled by their "
            "declared status.",
        }

    # -- data ------------------------------------------------------------------------------
    def _require_implemented(dataset_key: str) -> None:
        meta = get_dataset(dataset_key)
        if meta is None:
            raise UnknownDataset(f"Unknown dataset '{dataset_key}'.")
        if meta["status"] != "implemented":
            raise NotImplementedDataset(
                f"'{dataset_key}' is planned but not implemented yet.", details={"dataset": meta["collection_id"]}
            )

    @app.post("/api/layers/{dataset_key}", response_model=LayerResponse)
    def layer(
        dataset_key: str, body: MaiacLayerRequest, principal: Principal = Depends(compute_access)
    ) -> dict[str, Any]:
        _require_implemented(dataset_key)
        with compute_slots.slot():
            return maiac.layer(body, principal)

    @app.post("/api/stats/{dataset_key}/monthly", response_model=MonthlySeriesResponse)
    def monthly(dataset_key: str, body: MonthlySeriesRequest, _: Principal = Depends(compute_access)) -> dict[str, Any]:
        _require_implemented(dataset_key)
        with compute_slots.slot():
            return maiac.monthly(body)

    @app.post("/api/stats/{dataset_key}/monthly.csv", response_class=PlainTextResponse)
    def monthly_csv_export(
        dataset_key: str, body: MonthlySeriesRequest, _: Principal = Depends(compute_access)
    ) -> PlainTextResponse:
        _require_implemented(dataset_key)
        with compute_slots.slot():
            text = monthly_csv(maiac.monthly(body))
        filename = f"maiac_aod550_monthly_{body.start_month}_{body.end_month}.csv"
        return PlainTextResponse(
            text, media_type="text/csv", headers={"Content-Disposition": f'attachment; filename="{filename}"'}
        )

    @app.get("/api/tiles/{tile_id}/{z}/{x}/{y}.png")
    def tile(tile_id: str, z: int, x: int, y: int, principal: Principal = Depends(tile_access)) -> Response:
        requester = principal.id if settings.public else None
        try:
            png, _ = tiles.get_tile(tile_id, z, x, y, requester=requester)
        except ApiError:
            raise
        except Exception as exc:
            raise classify_ee_error(exc) from exc
        return Response(content=png, media_type="image/png", headers={"Cache-Control": "private, max-age=3600"})

    app.state.settings = settings
    app.state.runtime = runtime
    app.state.compute_slots = compute_slots
    return app


app = create_app()
