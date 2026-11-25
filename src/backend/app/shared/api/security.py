"""HTTP hardening (SEC-001, SEC-002): security headers and an Origin check on state-changing calls.

The session is an httpOnly SameSite=Lax cookie, which already stops classic cross-site form posts.
The Origin check is defence in depth: a browser always sends Origin on cross-origin POST/PUT/PATCH/
DELETE, so a request whose Origin is neither this API's own host nor an allowlisted frontend is
refused (403). Requests without Origin (curl, server-to-server, the test client) are unaffected.

"Same site" compares Origin with Host and with X-Forwarded-Host. The dev proxy rewrites Host to the API
address and forwards the browser's host as X-Forwarded-Host. A cross-site page cannot set that header:
it is not CORS-safelisted, so the browser preflights the request and this API's CORS allowlist blocks it.
"""

import logging
from collections.abc import Iterable
from urllib.parse import urlsplit

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

log = logging.getLogger("merchant_pay.security")
UNSAFE_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})
HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Permissions-Policy": "camera=(), microphone=(), geolocation=(), payment=()",
    "Cross-Origin-Opener-Policy": "same-origin",
}
# JSON API responses never need to load anything; the Swagger UI pages do, so they are exempt.
API_CSP = "default-src 'none'; frame-ancestors 'none'"
DOCS_PATHS = ("/api/docs", "/api/openapi.json", "/docs", "/redoc")


def _origin_of(url: str) -> str:
    parts = urlsplit(url)
    return f"{parts.scheme}://{parts.netloc}".lower()


class SecurityMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, allowed_origins: Iterable[str]) -> None:
        super().__init__(app)
        self._allowed = {_origin_of(o) for o in allowed_origins}

    def _origin_allowed(self, request: Request, origin: str) -> bool:
        if origin == "null":
            return False
        origin = _origin_of(origin)
        hosts = {request.headers.get("host", "").lower()}
        forwarded = request.headers.get("x-forwarded-host")
        if forwarded:
            hosts.add(forwarded.split(",")[0].strip().lower())
        return urlsplit(origin).netloc in hosts or origin in self._allowed

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        origin = request.headers.get("origin")
        refused = request.method in UNSAFE_METHODS and origin is not None \
            and not self._origin_allowed(request, origin)
        if refused:
            log.warning("cross-origin %s refused: origin=%s host=%s", request.method, origin,
                        request.headers.get("host"))
            response: Response = JSONResponse(
                {"detail": "Cross-origin request refused", "code": "OriginRefused"}, status_code=403)
        else:
            response = await call_next(request)
        for name, value in HEADERS.items():
            response.headers.setdefault(name, value)
        if not request.url.path.startswith(DOCS_PATHS):
            response.headers.setdefault("Content-Security-Policy", API_CSP)
        return response
