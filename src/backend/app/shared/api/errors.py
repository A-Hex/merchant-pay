"""Consistent error envelope + no internal leakage.

Every error response has the same shape::

    {"detail": <message | list of field errors>, "code": <stable machine code>,
     "request_id": <correlation id>}

5xx errors never include the exception text or a stack trace; the details go to the
structured server log, keyed by the same request id.
"""

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.shared.domain.errors import (
    DomainError,
    Forbidden,
    InvalidCredentials,
    InvalidStateTransition,
    NotFound,
    RateLimited,
)

_LOG = logging.getLogger("merchant_pay.errors")

_STATUS = [
    (InvalidCredentials, 401),
    (Forbidden, 403),
    (NotFound, 404),
    (InvalidStateTransition, 409),
    (RateLimited, 429),
    (DomainError, 422),
]


def _request_id(request: Request) -> str:
    return getattr(request.state, "request_id", "") or request.headers.get("x-request-id", "")


def _payload(request: Request, detail, code: str) -> dict:
    return {"detail": detail, "code": code, "request_id": _request_id(request)}


def register_error_handlers(app: FastAPI) -> None:
    async def handle_domain(request: Request, exc: Exception) -> JSONResponse:
        status_code = next(c for t, c in _STATUS if isinstance(exc, t))
        headers = {"Retry-After": str(exc.retry_after)} if isinstance(exc, RateLimited) else None
        return JSONResponse(
            status_code=status_code,
            content=_payload(request, str(exc), type(exc).__name__),
            headers=headers,
        )

    async def handle_validation(request: Request, exc: RequestValidationError) -> JSONResponse:
        # Strip non-JSON-serialisable context (e.g. the original ValueError) from errors.
        fields = [
            {"loc": list(err.get("loc", ())), "msg": str(err.get("msg", "")),
             "type": str(err.get("type", ""))}
            for err in exc.errors()
        ]
        return JSONResponse(
            status_code=422,
            content=_payload(request, fields, "ValidationError"),
        )

    async def handle_unexpected(request: Request, exc: Exception) -> JSONResponse:
        _LOG.exception("unhandled_exception", extra={"request_id": _request_id(request)})
        return JSONResponse(
            status_code=500,
            content=_payload(request, "Internal server error", "InternalError"),
        )

    app.add_exception_handler(DomainError, handle_domain)
    app.add_exception_handler(RequestValidationError, handle_validation)
    app.add_exception_handler(Exception, handle_unexpected)
