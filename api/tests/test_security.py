"""Public-mode hooks: authentication, authorisation, rate and concurrency limits, disclosure."""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.security import IAP_CERTS_URL, IapAuthenticator, Principal

from .conftest import FakeEngine, FakeRuntime, make_settings, roi_payload

APRIL = {"start": "2025-04-01", "end_exclusive": "2025-05-01"}
LAYER = "/api/layers/maiac_aod550"


class HeaderAuth:
    """Test authenticator: trusts x-test-user. NEVER use outside tests."""

    def authenticate(self, headers: dict[str, str]) -> Principal | None:
        user = headers.get("x-test-user")
        return Principal(user, authenticated=True) if user else None


class Clock:
    def __init__(self) -> None:
        self.t = 1000.0

    def __call__(self) -> float:
        return self.t


def public_client(
    tmp_path: Path, engine: FakeEngine | None = None, clock: Clock | None = None, **overrides: object
) -> TestClient:
    settings = make_settings(
        tmp_path, app_mode="public", auth_provider="iap", iap_audience="/projects/x/test", **overrides
    )
    app = create_app(
        settings,
        runtime=FakeRuntime(),
        engine_factory=lambda: engine or FakeEngine(),  # type: ignore[arg-type]
        authenticator=HeaderAuth(),
        clock=clock,
    )
    return TestClient(app)


def as_user(name: str) -> dict[str, str]:
    return {"x-test-user": name}


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"auth_provider": "none"}, "requires AUTH_PROVIDER"),
        ({"auth_provider": "iap", "iap_audience": None}, "IAP_AUDIENCE"),
        ({"auth_provider": "iap", "iap_audience": "a", "allowed_origins": ("*",)}, "explicit origins"),
    ],
)
def test_public_mode_refuses_unsafe_configuration(tmp_path: Path, overrides: dict, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        create_app(make_settings(tmp_path, app_mode="public", **overrides))


def test_public_mode_requires_authentication(tmp_path: Path) -> None:
    client = public_client(tmp_path)
    for method, path, kw in [
        ("get", "/api/datasets", {}),
        ("get", "/api/methods", {}),
        ("get", "/api/rois", {}),
        ("post", LAYER, {"json": {"roi": roi_payload(), **APRIL}}),
        ("get", "/api/tiles/abc/8/1/1.png", {}),
    ]:
        res = getattr(client, method)(path, **kw)
        assert res.status_code == 401 and res.json()["error"]["code"] == "UNAUTHENTICATED", path
    assert client.get("/api/docs").status_code == 404 and client.get("/api/openapi.json").status_code == 404


def test_health_discloses_diagnostics_only_to_authorised_principals(tmp_path: Path) -> None:
    client = public_client(tmp_path, authorized_principals=("alice",))
    assert client.get("/api/health").json() == {"status": "ok"}
    assert client.get("/api/health", headers=as_user("mallory")).json() == {"status": "ok"}
    full = client.get("/api/health", headers=as_user("alice")).json()
    assert full["app_mode"] == "public" and "earth_engine" in full


def test_authorisation_allowlist(tmp_path: Path) -> None:
    client = public_client(tmp_path, authorized_principals=("alice",))
    assert client.get("/api/datasets", headers=as_user("mallory")).status_code == 403
    assert client.get("/api/datasets", headers=as_user("Alice")).status_code == 200


def test_rate_limit(tmp_path: Path) -> None:
    clock = Clock()
    client = public_client(tmp_path, clock=clock, rate_limit_compute_per_min=2)
    body = {"roi": roi_payload(), **APRIL}
    assert client.post(LAYER, json=body, headers=as_user("alice")).status_code == 200
    assert client.post(LAYER, json=body, headers=as_user("alice")).status_code == 200
    third = client.post(LAYER, json=body, headers=as_user("alice"))
    assert third.status_code == 429 and third.json()["error"]["code"] == "RATE_LIMITED"
    assert client.post(LAYER, json=body, headers=as_user("bob")).status_code == 200  # per principal
    clock.t += 61
    assert client.post(LAYER, json=body, headers=as_user("alice")).status_code == 200


def test_concurrency_limit(tmp_path: Path) -> None:
    client = public_client(tmp_path, max_concurrent_compute=1, compute_queue_timeout_s=0.01)
    slots = client.app.state.compute_slots  # type: ignore[attr-defined]
    with slots.slot():  # simulate a computation already running
        busy = client.post(LAYER, json={"roi": roi_payload(), **APRIL}, headers=as_user("alice"))
    assert busy.status_code == 503 and busy.json()["error"]["code"] == "SERVER_BUSY"
    assert client.post(LAYER, json={"roi": roi_payload(), **APRIL}, headers=as_user("alice")).status_code == 200


def test_tiles_and_layer_cache_are_scoped_to_principal(tmp_path: Path) -> None:
    client = public_client(tmp_path)
    body = {"roi": roi_payload(), **APRIL}
    a = client.post(LAYER, json=body, headers=as_user("alice")).json()["layers"][0]["tile_url_template"]
    b = client.post(LAYER, json=body, headers=as_user("bob")).json()["layers"][0]["tile_url_template"]
    assert a != b  # cached responses are not shared across principals
    url = a.format(z=8, x=203, y=93)
    assert client.get(url, headers=as_user("alice")).status_code == 200
    stolen = client.get(url, headers=as_user("bob"))
    assert stolen.status_code == 410 and stolen.json()["error"]["code"] == "TILE_EXPIRED"


def test_earth_engine_error_details_hidden_in_public_mode(tmp_path: Path) -> None:
    class Failing(FakeEngine):
        def period_stats(self, *args: object, **kwargs: object) -> dict:
            raise RuntimeError("Quota exceeded for project my-secret-project")

    client = public_client(tmp_path, engine=Failing())
    res = client.post(LAYER, json={"roi": roi_payload(), **APRIL}, headers=as_user("alice"))
    assert res.status_code == 429
    assert res.json()["error"]["details"] is None and "my-secret-project" not in res.text


def test_local_mode_keeps_details_for_the_researcher(tmp_path: Path) -> None:
    class Failing(FakeEngine):
        def period_stats(self, *args: object, **kwargs: object) -> dict:
            raise RuntimeError("Computation timed out.")

    app = create_app(make_settings(tmp_path), runtime=FakeRuntime(), engine_factory=lambda: Failing())  # type: ignore[arg-type]
    res = TestClient(app).post(LAYER, json={"roi": roi_payload(), **APRIL})
    assert res.status_code == 504 and "timed out" in res.json()["error"]["details"]


def test_iap_authenticator_uses_signed_assertion_only(monkeypatch: pytest.MonkeyPatch) -> None:
    from google.oauth2 import id_token

    seen: dict[str, object] = {}

    def fake_verify(token: str, request: object, audience: str, certs_url: str) -> dict[str, str]:
        seen.update(token=token, audience=audience, certs_url=certs_url)
        if token != "good":
            raise ValueError("bad signature")
        return {"email": "alice@example.org", "sub": "123"}

    monkeypatch.setattr(id_token, "verify_token", fake_verify)
    auth = IapAuthenticator("/projects/1/global/backendServices/2")
    assert auth.authenticate({}) is None
    assert auth.authenticate({"x-goog-authenticated-user-email": "accounts.google.com:eve@x"}) is None
    assert auth.authenticate({"x-goog-iap-jwt-assertion": "forged"}) is None
    principal = auth.authenticate({"x-goog-iap-jwt-assertion": "good"})
    assert principal == Principal("alice@example.org", True)
    assert seen["audience"] == "/projects/1/global/backendServices/2" and seen["certs_url"] == IAP_CERTS_URL
