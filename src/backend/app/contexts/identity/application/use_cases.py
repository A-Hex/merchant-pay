from dataclasses import dataclass

from app.contexts.identity.application.ports import (
    AccessRepository,
    LoginThrottle,
    MerchantRepository,
    PasswordHasher,
    TokenService,
    UserRepository,
)
from app.contexts.identity.domain.model import (
    Merchant,
    MerchantAccess,
    MerchantChanges,
    Role,
    User,
    can_edit_profile,
)
from app.shared.domain.errors import DomainError, Forbidden, InvalidCredentials, NotFound
from app.shared.domain.merchant_scope import MerchantScope


@dataclass(frozen=True, slots=True)
class IssuedSession:
    token: str
    user_id: int


class Authenticate:
    """Verify credentials and mint a session token.

    * Per-IP/per-account throttling runs first, so brute force is stopped before hashing.
    * A missing account is verified against a decoy hash, so a wrong email and a wrong
      password take the same time (no account enumeration through latency).
    * The error message is identical for every failure mode.
    """

    def __init__(self, users: UserRepository, hasher: PasswordHasher, tokens: TokenService,
                 throttle: LoginThrottle | None = None) -> None:
        self._users, self._hasher, self._tokens = users, hasher, tokens
        self._throttle = throttle

    def execute(self, email: str, password: str, client_ip: str = "unknown") -> IssuedSession:
        normalized = email.strip().lower()
        if self._throttle:
            self._throttle.ensure_allowed(client_ip, normalized)

        user = self._users.get_by_email(normalized)
        password_hash = user.password_hash if user is not None else self._hasher.decoy_hash
        password_ok = self._hasher.verify(password, password_hash)

        if user is None or not user.is_active or not password_ok:
            if self._throttle:
                self._throttle.record_failure(client_ip, normalized)
            raise InvalidCredentials()  # same error whatever failed: no account enumeration

        if self._throttle:
            self._throttle.record_success(client_ip, normalized)
        return IssuedSession(token=self._tokens.issue(user.id), user_id=user.id)


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
    """Owner-only profile update; the request session owns the transaction boundary."""

    def __init__(self, merchants: MerchantRepository) -> None:
        self._merchants = merchants

    def execute(self, scope: MerchantScope, changes: MerchantChanges) -> Merchant:
        if not can_edit_profile(Role(scope.role)):
            raise Forbidden("Only the merchant owner can edit the profile")
        if changes.is_empty:
            raise DomainError("No fields to update")
        merchant = self._merchants.update(scope.merchant_id, changes)
        if merchant is None:
            raise NotFound("Merchant not found")
        return merchant