from fastapi import APIRouter, Depends, Response, status
from pydantic import BaseModel, Field

from app.config import Settings, get_settings
from app.container import SESSION_COOKIE, get_authenticate, get_me_uc, get_scope
from app.contexts.identity.application.use_cases import Authenticate, GetMe
from app.shared.api.schemas import MoneyOut
from app.shared.domain.merchant_scope import MerchantScope

router = APIRouter(tags=["identity"])


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
def login(body: LoginIn, response: Response, uc: Authenticate = Depends(get_authenticate),
          settings: Settings = Depends(get_settings)) -> None:
    # TODO(stretch): rate-limit login attempts per IP/email.
    token = uc.execute(body.email, body.password)
    response.set_cookie(SESSION_COOKIE, token, httponly=True, samesite="lax",
                        secure=settings.cookie_secure, max_age=settings.jwt_ttl_minutes * 60)


@router.post("/auth/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(response: Response) -> None:
    response.delete_cookie(SESSION_COOKIE)


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


# TODO(Person A): PATCH /merchant/me -> UpdateMerchantProfile
