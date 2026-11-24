from dataclasses import dataclass

from app.contexts.identity.application.ports import (
    AccessRepository,
    MerchantRepository,
    PasswordHasher,
    TokenService,
    UserRepository,
)
from app.contexts.identity.domain.model import Merchant, MerchantAccess, User
from app.shared.domain.errors import Forbidden, InvalidCredentials, NotFound
from app.shared.domain.merchant_scope import MerchantScope
from app.shared.domain.money import Money


class Authenticate:
    def __init__(self, users: UserRepository, hasher: PasswordHasher, tokens: TokenService) -> None:
        self._users, self._hasher, self._tokens = users, hasher, tokens

    def execute(self, email: str, password: str) -> str:
        user = self._users.get_by_email(email.strip().lower())
        if user is None or not user.is_active or not self._hasher.verify(password, user.password_hash):
            raise InvalidCredentials()  # same error whatever failed: no account enumeration
        return self._tokens.issue(user.id)


class ResolveScope:
    """The ONLY producer of MerchantScope. Server-side mapping is the authority."""

    def __init__(self, access: AccessRepository) -> None:
        self._access = access

    def execute(self, user_id: int, requested_merchant_id: str | None = None) -> MerchantScope:
        grants = self._access.for_user(user_id)
        if not grants:
            raise Forbidden("No merchant assigned to this user")
        if requested_merchant_id is None:
            grant = grants[0]
        else:
            grant = next((g for g in grants if g.merchant_id == requested_merchant_id), None)
            if grant is None:
                raise Forbidden("Merchant not accessible")
        return MerchantScope(user_id=user_id, merchant_id=grant.merchant_id, role=grant.role.value)


@dataclass(frozen=True, slots=True)
class Me:
    user: User
    merchant: Merchant
    accessible: list[MerchantAccess]


class GetMe:
    def __init__(self, users: UserRepository, access: AccessRepository,
                 merchants: MerchantRepository) -> None:
        self._users, self._access, self._merchants = users, access, merchants

    def execute(self, scope: MerchantScope) -> Me:
        user = self._users.get(scope.user_id)
        merchant = self._merchants.get(scope.merchant_id)
        if user is None or merchant is None:
            raise NotFound("Profile not found")
        return Me(user, merchant, self._access.for_user(scope.user_id))


class UpdateMerchantProfile:
    def __init__(self, merchants: MerchantRepository) -> None:
        self._merchants = merchants

    def execute(self, merchant_id: str, data: dict) -> Merchant:
        merchant = self._merchants.get(merchant_id)
        if merchant is None:
            raise Exception("Merchant not found")
        updates: dict = {}
        if "display_name" in data:
            updates["display_name"] = data["display_name"]
        if "category" in data:
            updates["category"] = data["category"]
        if "operating_days" in data:
            updates["operating_days"] = ",".join(data["operating_days"])
        if "monthly_goal_centimes" in data:
            updates["monthly_goal_centimes"] = data["monthly_goal_centimes"]
        for key, value in updates.items():
            setattr(merchant, key, value)
        self._merchants._s.add(merchant)
        self._merchants._s.commit()
        self._merchants._s.refresh(merchant)
        return Merchant(
            merchant_id=merchant.merchant_id,
            display_name=merchant.display_name,
            category=merchant.category,
            timezone=merchant.timezone,
            operating_days=tuple(d for d in merchant.operating_days.split(",") if d),
            monthly_goal=Money(merchant.monthly_goal_centimes)
        if merchant.monthly_goal_centimes is not None
        else None,
        )