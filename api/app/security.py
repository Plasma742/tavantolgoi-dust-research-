"""Access control and abuse limits for a FUTURE public mode.

``APP_MODE=local`` (default): single researcher on 127.0.0.1, no authentication.
``APP_MODE=public``: every endpoint except a minimal health check requires an authenticated,
authorised principal; the app refuses to start without an authentication provider.

None of this makes a deployment safe on its own. See docs/DEPLOYMENT_CHECKLIST.md:
CORS is not authentication, and the request-size limit here must be backed by the reverse
proxy / load balancer.
"""

from __future__ import annotations

import threading
import time
from collections import deque
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any, Protocol

from .errors import ApiError

IAP_JWT_HEADER = "x-goog-iap-jwt-assertion"
IAP_CERTS_URL = "https://www.gstatic.com/iap/verify/public_key"


@dataclass(frozen=True)
class Principal:
    id: str
    authenticated: bool


LOCAL_PRINCIPAL = Principal("local", authenticated=False)


class Authenticator(Protocol):
    def authenticate(self, headers: dict[str, str]) -> Principal | None: ...


class IapAuthenticator:
    """Verifies the signed JWT that Google Identity-Aware Proxy adds to each request.

    Only the signed assertion is trusted; plain identity headers are ignored because a client
    could forge them if the proxy were bypassed.
    """

    def __init__(self, audience: str):
        self._audience = audience

    def authenticate(self, headers: dict[str, str]) -> Principal | None:
        token = headers.get(IAP_JWT_HEADER)
        if not token:
            return None
        try:
            from google.auth.transport import requests as google_requests
            from google.oauth2 import id_token

            claims = id_token.verify_token(
                token, google_requests.Request(), audience=self._audience, certs_url=IAP_CERTS_URL
            )
        except Exception:  # invalid signature, audience, expiry or network failure -> unauthenticated
            return None
        subject = claims.get("email") or claims.get("sub")
        return Principal(str(subject), authenticated=True) if subject else None


class Unauthenticated(ApiError):
    status_code = 401
    code = "UNAUTHENTICATED"


class Forbidden(ApiError):
    status_code = 403
    code = "FORBIDDEN"


class RateLimited(ApiError):
    status_code = 429
    code = "RATE_LIMITED"


class ServerBusy(ApiError):
    status_code = 503
    code = "SERVER_BUSY"


class RateLimiter:
    """Sliding one-minute window per key. ``per_minute <= 0`` disables the limit."""

    def __init__(self, per_minute: int, clock: Callable[[], float] = time.monotonic):
        self.per_minute = per_minute
        self._clock = clock
        self._hits: dict[str, deque[float]] = {}
        self._lock = threading.Lock()

    def check(self, key: str) -> None:
        if self.per_minute <= 0:
            return
        now = self._clock()
        with self._lock:
            hits = self._hits.setdefault(key, deque())
            while hits and now - hits[0] >= 60.0:
                hits.popleft()
            if len(hits) >= self.per_minute:
                raise RateLimited(f"Rate limit of {self.per_minute} requests per minute reached. Retry shortly.")
            hits.append(now)


class ComputeLimiter:
    """Bounds concurrent Earth Engine computations; waits up to ``queue_timeout_s`` for a slot."""

    def __init__(self, max_concurrent: int, queue_timeout_s: float):
        self.max_concurrent = max(1, max_concurrent)
        self.queue_timeout_s = queue_timeout_s
        self._sem = threading.BoundedSemaphore(self.max_concurrent)

    @contextmanager
    def slot(self) -> Iterator[None]:
        if not self._sem.acquire(timeout=self.queue_timeout_s):
            raise ServerBusy("Too many Earth Engine computations in progress. Retry shortly.")
        try:
            yield
        finally:
            self._sem.release()


class BodySizeLimitMiddleware:
    """Pure ASGI middleware that bounds the request body by counting the bytes actually
    received (so chunked uploads without Content-Length are bounded too). The body, at most
    ``max_bytes``, is buffered and replayed to the app. A reverse-proxy limit is still required
    because this runs only after the server has accepted the connection."""

    def __init__(self, app: Any, max_bytes: int):
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope: dict[str, Any], receive: Any, send: Any) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        for name, value in scope.get("headers", []):
            if name == b"content-length" and value.isdigit() and int(value) > self.max_bytes:
                await self._reject(send)
                return
        messages: list[dict[str, Any]] = []
        received = 0
        while True:
            message = await receive()
            messages.append(message)
            if message["type"] != "http.request":
                break
            received += len(message.get("body", b""))
            if received > self.max_bytes:
                await self._reject(send)
                return
            if not message.get("more_body", False):
                break

        async def replay() -> dict[str, Any]:
            if messages:
                return messages.pop(0)
            return await receive()

        await self.app(scope, replay, send)

    async def _reject(self, send: Any) -> None:
        body = (
            b'{"error":{"code":"PAYLOAD_TOO_LARGE","message":"Request body larger than '
            + str(self.max_bytes).encode()
            + b' bytes.","details":null}}'
        )
        await send(
            {
                "type": "http.response.start",
                "status": 413,
                "headers": [(b"content-type", b"application/json"), (b"content-length", str(len(body)).encode())],
            }
        )
        await send({"type": "http.response.body", "body": body})
