from typing import Literal

from fastapi import APIRouter, Depends, Request, Response, status
from pydantic import BaseModel, ConfigDict, Field

from app.config import Settings, get_settings
from app.container import (
    get_audit_repository,
    get_authenticate,
    get_me_uc,
    get_scope,
    get_update_merchant_profile,
    require_roles,
)
from app.contexts.identity.application.use_cases import Authenticate, GetMe, UpdateMerchantProfile
from app.contexts.identity.domain.model import Merchant, MerchantChanges
from app.shared.api.schemas import MoneyOut
from app.shared.audit import SqlAuditRepository
from app.shared.domain.merchant_scope import MerchantScope

router = APIRouter(tags=["identity"])

Weekday = Literal["mon", "tue", "wed", "thu", "fri", "sat", "sun"]


class LoginIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=128)


class MerchantOut(BaseModel):
    merchant_id: str
    display_name: str
    category: str
    timezone: str
    operating_days: list[str]
    monthly_goal: MoneyOut | None

    @classmethod
    def of(cls, m: Merchant) -> "MerchantOut":
        return cls(
            merchant_id=m.merchant_id, display_name=m.display_name, category=m.category,
            timezone=m.timezone, operating_days=list(m.operating_days),
            monthly_goal=MoneyOut.of(m.monthly_goal) if m.monthly_goal else None,
        )


class MerchantUpdateIn(BaseModel):
    """Strict partial update: unknown fields are rejected instead of silently ignored."""

    model_config = ConfigDict(extra="forbid")

    display_name: str | None = Field(default=None, min_length=1, max_length=200)
    category: str | None = Field(default=None, min_length=1, max_length=100)
    operating_days: list[Weekday] | None = Field(default=None, min_length=1, max_length=7)
    monthly_goal_centimes: int | None = Field(default=None, ge=0, le=100_000_000_000)

    def to_changes(self) -> MerchantChanges:
        return MerchantChanges(
            display_name=self.display_name.strip() if self.display_name is not None else None,
            category=self.category.strip() if self.category is not None else None,
            operating_days=tuple(self.operating_days) if self.operating_days is not None else None,
            monthly_goal_centimes=self.monthly_goal_centimes,
            monthly_goal_provided="monthly_goal_centimes" in self.model_fields_set,
        )


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
          settings: Settings = Depends(get_settings),
          audit: SqlAuditRepository = Depends(get_audit_repository)) -> None:
    client_ip = request.client.host if request.client else "unknown"
    session = uc.execute(body.email, body.password, client_ip=client_ip)
    audit.record(session.user_id, "auth.login_succeeded", f"user:{session.user_id}")
    response.set_cookie(
        settings.cookie_name,
        session.token,
        max_age=settings.jwt_ttl_minutes * 60,
        httponly=True,
        secure=settings.cookie_secure,
        samesite=settings.cookie_samesite,
        domain=settings.cookie_domain,
        path="/",
    )


@router.post("/auth/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(response: Response, settings: Settings = Depends(get_settings)) -> None:
    # Stateless JWT: the cookie is cleared client-side. Server-side revocation would need a
    # token denylist; documented as a known limitation rather than pretended.
    response.delete_cookie(settings.cookie_name, path="/", domain=settings.cookie_domain,
                           secure=settings.cookie_secure, httponly=True,
                           samesite=settings.cookie_samesite)


@router.get("/merchant/me", response_model=MeOut)
def me(scope: MerchantScope = Depends(get_scope), uc: GetMe = Depends(get_me_uc)) -> MeOut:
    result = uc.execute(scope)
    return MeOut(
        email=result.user.email,
        role=scope.role,
        merchant=MerchantOut.of(result.merchant),
        accessible_merchants=[AccessOut(merchant_id=a.merchant_id, role=a.role.value)
                              for a in result.accessible],
    )


@router.patch("/merchant/me", response_model=MerchantOut)
def me_patch(body: MerchantUpdateIn,
             scope: MerchantScope = Depends(require_roles("owner")),
             uc: UpdateMerchantProfile = Depends(get_update_merchant_profile),
             audit: SqlAuditRepository = Depends(get_audit_repository)) -> MerchantOut:
    merchant = uc.execute(scope, body.to_changes())
    audit.record(scope.user_id, "merchant.profile_updated", f"merchant:{merchant.merchant_id}")
    return MerchantOut.of(merchant)
