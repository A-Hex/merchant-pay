"""Request correlation, structured access logs and browser hardening headers."""

import json
import logging
import time
from datetime import UTC, datetime
from uuid import uuid4

from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

_ACCESS = logging.getLogger("merchant_pay.access")
_SECURITY = logging.getLogger("merchant_pay.security")

_SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS", "TRACE"})

# Sent on every API response. The CSP is deliberately restrictive: this service returns
# JSON only (the interactive docs are served outside the /api/v1 prefix).
_CSP = "default-src 'none'; frame-ancestors 'none'; base-uri 'none'"


class JsonFormatter(logging.Formatter):
    """One JSON object per line, so logs are queryable by request_id in any aggregator."""

    _EXTRA = ("request_id", "method", "path", "status", "duration_ms", "client_ip",
              "user_id", "action", "merchant_id")

    def format(self, record: logging.LogRecord) -> str:
        payload: dict = {
            "ts": datetime.now(UTC).isoformat(timespec="milliseconds"),
            "level": record.levelname,
            "logger": record.name,
            "event": record.getMessage(),
        }
        for key in self._EXTRA:
            value = getattr(record, key, None)
            if value is not None:
                payload[key] = value
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str, ensure_ascii=False)


def configure_logging(level: int = logging.INFO) -> None:
    """Install JSON logging unless the host already configured logging (pytest, gunicorn)."""
    root = logging.getLogger()
    if root.handlers:
        return
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    root.addHandler(handler)
    root.setLevel(level)
    # Uvicorn's access log duplicates ours and is not structured.
    logging.getLogger("uvicorn.access").disabled = True


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Adds request ids, blocks cross-origin unsafe requests, logs and hardens responses."""

    def __init__(self, app, *, allowed_origins: list[str], https_only: bool = False) -> None:
        super().__init__(app)
        self._origins = frozenset(allowed_origins)
        self._https_only = https_only

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        request_id = (request.headers.get("x-request-id") or "").strip()[:64] or uuid4().hex
        request.state.request_id = request_id
        client_ip = request.client.host if request.client else "unknown"

        # CSRF defence in depth (cookies are SameSite=Lax already): a browser request that
        # carries a foreign Origin is rejected before it reaches any handler.
        origin = request.headers.get("origin")
        if request.method not in _SAFE_METHODS and origin and origin not in self._origins:
            _SECURITY.warning(
                "cross_origin_request_rejected",
                extra={"request_id": request_id, "method": request.method,
                       "path": request.url.path, "client_ip": client_ip},
            )
            response = JSONResponse(
                status_code=403,
                content={"detail": "Cross-origin request rejected", "code": "OriginRejected",
                         "request_id": request_id},
            )
            self._harden(response, request_id)
            return response

        started = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            _ACCESS.exception(
                "request_failed",
                extra={"request_id": request_id, "method": request.method,
                       "path": request.url.path, "client_ip": client_ip},
            )
            raise

        duration_ms = round((time.perf_counter() - started) * 1000, 2)
        self._harden(response, request_id)
        _ACCESS.info(
            "request",
            extra={"request_id": request_id, "method": request.method,
                   "path": request.url.path, "status": response.status_code,
                   "duration_ms": duration_ms, "client_ip": client_ip},
        )
        return response

    def _harden(self, response: Response, request_id: str) -> None:
        headers = {
            "X-Request-ID": request_id,
            "X-Content-Type-Options": "nosniff",
            "X-Frame-Options": "DENY",
            "Referrer-Policy": "no-referrer",
            "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
            "Cache-Control": "no-store",
            "Content-Security-Policy": _CSP,
        }
        if self._https_only:
            headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        for key, value in headers.items():
            response.headers.setdefault(key, value)
