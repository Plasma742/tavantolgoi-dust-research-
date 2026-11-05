# Deployment checklist — NOT READY FOR PUBLIC DEPLOYMENT

**Status (method `maiac-aod550/0.2.0`):** local research prototype only. No public URL may be created until every item below is done and reviewed. The default `APP_MODE=local` assumes one researcher on `127.0.0.1` and has **no authentication**.

## Review gates (scientific)

- [ ] Live acceptance parity evidence is recorded with `result: PASS` (README › Acceptance) for a verified ROI and April 2025.
- [ ] The methodology owner has signed off on method `maiac-aod550/0.2.0` (variants, QA guard, definitions).
- [ ] Data rights, citations and ROI publication permissions are confirmed; restricted geometry is not in the repository.

## Access control

- [ ] `APP_MODE=public` is set. The app **refuses to start** in public mode without `AUTH_PROVIDER`, without `IAP_AUDIENCE`, or with a `*` CORS origin.
- [ ] Authentication: Google Identity-Aware Proxy (IAP) in front of Cloud Run with `AUTH_PROVIDER=iap`. The backend verifies the **signed** `x-goog-iap-jwt-assertion` (audience = `IAP_AUDIENCE`) and ignores unsigned identity headers. Cloud Run ingress must allow only the load balancer, so IAP cannot be bypassed.
- [ ] Authorisation: `AUTHORIZED_PRINCIPALS` lists the allowed accounts. If it is empty, *any* IAP-authenticated user is allowed; avoid that.
- [ ] **CORS is not authentication.** It only controls which browser origins may read responses; scripts and other non-browser clients ignore it.

## Abuse and quota limits

- [ ] Rate limits: `RATE_LIMIT_COMPUTE_PER_MIN` and `RATE_LIMIT_TILES_PER_MIN` are applied per principal, but only **per instance** (in-process). With more than one instance, add a shared limit as well: Cloud Armor rate-based rules or an API gateway.
- [ ] Concurrency/queue: `MAX_CONCURRENT_COMPUTE` slots per instance; requests wait up to `COMPUTE_QUEUE_TIMEOUT_S`, then get `503 SERVER_BUSY`. Cap Cloud Run max instances × slots so total Earth Engine parallelism stays within the project's EECU quota.
- [ ] Request size: the app rejects bodies over `MAX_REQUEST_BYTES` using both Content-Length and the bytes actually streamed (chunked uploads). **This application-level check is not sufficient on its own**: it runs only after the server has accepted the request and has no control over slow or oversized uploads at the network edge. Enforce a body-size limit at the load balancer / reverse proxy as well (for example, nginx `client_max_body_size` or the equivalent proxy setting).
- [ ] ROI, period and series bounds (`MAX_ROI_AREA_KM2`, `ALLOWED_BBOX`, `MAX_LAYER_DAYS`, `MAX_SERIES_MONTHS`) are reviewed for the public use case.

## Reviewed behaviours (findings from the 2026-11-04 review)

| Area | Behaviour | Remaining risk / action |
| --- | --- | --- |
| Tile tokens | 192-bit random ids held in process memory; expire after `LAYER_CACHE_TTL_S + 300 s` or on restart. Each is a bearer token for one rendered image. In public mode an id is bound to its creating principal; other principals get `410 TILE_EXPIRED`, the same answer as for an unknown id. | Ids are not shared across instances: use session affinity or a shared store. Never log tile URLs. |
| Cache scope | The stats cache is keyed by method version + ROI geometry hash + period. Sharing it is safe because a requester only receives numbers for geometry they submitted themselves. The layer cache is also keyed by principal in public mode. ROI labels and status are re-attached per request, never taken from another user's request. | Caches are per instance and in memory. Restricted geometry is hashed in cache keys and is not logged by the app. |
| Health endpoint | Public mode returns only `{"status": "ok"}` to unauthenticated or unauthorised callers. Diagnostics (Earth Engine status message, auth mode, code revision, limits) go only to authorised principals. Local mode shows them to the local researcher. | Keep the endpoint unauthenticated only if the load balancer needs it; restrict it otherwise. |
| Error details | In public mode, Earth Engine error details are logged server-side and removed from responses. | Review log retention and access. |
| API docs | `/api/docs` and `/api/openapi.json` are disabled in public mode. | — |

## Secrets and infrastructure

- [ ] Cloud Run uses its service identity (`EE_AUTH_MODE=adc`). No key files exist in the image or repository; CI's secret guard passes.
- [ ] IAM grants only the roles that the current Earth Engine service-account guide requires.
- [ ] Logs do not record request bodies (ROI geometry may be restricted).
- [ ] The basemap provider's terms permit the intended use; `VITE_BASEMAP_URL` is set accordingly.
- [ ] `CODE_REVISION` is passed at build time so provenance records the deployed commit.
