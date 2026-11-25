import logging
from datetime import UTC, datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query, Request, Response, status
from pydantic import BaseModel, ConfigDict, Field

from app.config import Settings, get_settings
from app.container import (
    SESSION_COOKIE,
    LoginThrottle,
    get_authenticate,
    get_current_user_id,
    get_login_history_uc,
    get_login_throttle,
    get_me_uc,
    get_record_login_event,
    get_scope,
    get_token_service,
    get_update_merchant_profile,
)
from app.contexts.identity.application.use_cases import (
    Authenticate,
    GetLoginHistory,
    GetMe,
    ProfileChanges,
    RecordLoginEvent,
    UpdateMerchantProfile,
)
from app.contexts.identity.domain.model import (
    LOGIN_HISTORY_RETENTION_DAYS,
    LoginOutcome,
    Merchant,
    device_label,
)
from app.shared.api.schemas import MoneyOut
from app.shared.domain.errors import InvalidCredentials, TooManyAttempts
from app.shared.domain.merchant_scope import MerchantScope
from app.shared.domain.money import Money

router = APIRouter(tags=["identity"])
log = logging.getLogger("merchant_pay.auth")


class LoginIn(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=128)


class MerchantOut(BaseModel):
    merchant_id: str
    display_name: str
    category: str
    timezone: str
    operating_days: list[str]
    monthly_goal: MoneyOut | None


class AccessOut(BaseModel):
    merchant_id: str
    role: str


class MeOut(BaseModel):
    email: str
    role: str
    merchant: MerchantOut
    accessible_merchants: list[AccessOut]


@router.post("/auth/login", status_code=status.HTTP_204_NO_CONTENT)
def login(body: LoginIn, request: Request, response: Response,
          uc: Authenticate = Depends(get_authenticate),
          throttle: LoginThrottle = Depends(get_login_throttle),
          events: RecordLoginEvent = Depends(get_record_login_event),
          settings: Settings = Depends(get_settings)) -> None:
    # Direct peer address. Behind a reverse proxy, configure uvicorn --proxy-headers with trusted IPs.
    ip = request.client.host if request.client else "unknown"
    agent = request.headers.get("user-agent", "")
    now = datetime.now(UTC)
    wait = throttle.retry_after(body.email, ip)
    if wait is not None:
        log.warning("login throttled ip=%s retry_after=%ss", ip, wait)
        events.for_email(body.email, LoginOutcome.THROTTLED, ip, agent, now)
        raise TooManyAttempts(wait)
    try:
        token = uc.execute(body.email, body.password)
    except InvalidCredentials:
        throttle.record_failure(body.email, ip)
        events.for_email(body.email, LoginOutcome.FAILURE, ip, agent, now)
        raise
    throttle.reset(body.email, ip)
    events.for_email(body.email, LoginOutcome.SUCCESS, ip, agent, now)
    response.set_cookie(SESSION_COOKIE, token, httponly=True, samesite="lax",
                        secure=settings.cookie_secure, max_age=settings.jwt_ttl_minutes * 60)


@router.post("/auth/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(request: Request, response: Response, tokens=Depends(get_token_service),
           events: RecordLoginEvent = Depends(get_record_login_event)) -> None:
    token = request.cookies.get(SESSION_COOKIE)
    user_id = tokens.decode(token) if token else None
    if user_id is not None:
        events.for_user(user_id, LoginOutcome.LOGOUT, request.client.host if request.client else "unknown",
                        request.headers.get("user-agent", ""), datetime.now(UTC))
    response.delete_cookie(SESSION_COOKIE)


class LoginEventOut(BaseModel):
    occurred_at: datetime
    outcome: LoginOutcome
    ip: str
    device: str  # browser family and OS only, parsed from the User-Agent


class LoginHistoryOut(BaseModel):
    events: list[LoginEventOut]
    failures_last_30_days: int  # failed + throttled attempts on this account
    previous_success: datetime | None
    retention_days: int


@router.get("/auth/history", response_model=LoginHistoryOut)
def login_history(limit: Annotated[int, Query(ge=1, le=100)] = 20,
                  user_id: int = Depends(get_current_user_id),
                  uc: GetLoginHistory = Depends(get_login_history_uc)) -> LoginHistoryOut:
    """The signed-in user's own authentication events. Never another user's, whatever the merchant."""
    h = uc.execute(user_id, datetime.now(UTC), limit)
    return LoginHistoryOut(
        events=[LoginEventOut(occurred_at=e.occurred_at, outcome=e.outcome, ip=e.ip,
                              device=device_label(e.user_agent)) for e in h.events],
        failures_last_30_days=h.failures_last_30_days, previous_success=h.previous_success,
        retention_days=LOGIN_HISTORY_RETENTION_DAYS)


@router.get("/merchant/me", response_model=MeOut)
def me(scope: MerchantScope = Depends(get_scope), uc: GetMe = Depends(get_me_uc)) -> MeOut:
    result = uc.execute(scope)
    m = result.merchant
    return MeOut(
        email=result.user.email,
        role=scope.role,
        merchant=MerchantOut(
            merchant_id=m.merchant_id, display_name=m.display_name, category=m.category,
            timezone=m.timezone, operating_days=list(m.operating_days),
            monthly_goal=MoneyOut.of(m.monthly_goal) if m.monthly_goal else None,
        ),
        accessible_merchants=[AccessOut(merchant_id=a.merchant_id, role=a.role.value)
                              for a in result.accessible],
    )


Weekday = Literal["sun", "mon", "tue", "wed", "thu", "fri", "sat"]


class MerchantPatchIn(BaseModel):
    """Partial update: omitted fields are unchanged; monthly_goal_centimes=null clears the goal."""

    model_config = ConfigDict(extra="forbid")
    display_name: str | None = Field(default=None, min_length=1, max_length=200)
    category: str | None = Field(default=None, max_length=100)
    operating_days: list[Weekday] | None = Field(default=None, min_length=1, max_length=7)
    monthly_goal_centimes: int | None = Field(default=None, gt=0, le=10**14)


def _merchant_out(m: Merchant) -> MerchantOut:
    return MerchantOut(
        merchant_id=m.merchant_id, display_name=m.display_name, category=m.category,
        timezone=m.timezone, operating_days=list(m.operating_days),
        monthly_goal=MoneyOut.of(m.monthly_goal) if m.monthly_goal else None,
    )


@router.patch("/merchant/me", response_model=MerchantOut)
def me_patch(body: MerchantPatchIn, scope: MerchantScope = Depends(get_scope),
             uc: UpdateMerchantProfile = Depends(get_update_merchant_profile)) -> MerchantOut:
    sent = body.model_fields_set
    goal = body.monthly_goal_centimes
    changes = ProfileChanges(
        display_name=body.display_name,
        category=body.category,
        operating_days=tuple(body.operating_days) if body.operating_days is not None else None,
        monthly_goal=Money(goal) if goal is not None else None,
        clear_monthly_goal="monthly_goal_centimes" in sent and goal is None,
    )
    return _merchant_out(uc.execute(scope, changes))
