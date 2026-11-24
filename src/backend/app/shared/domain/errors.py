"""Domain errors. The API layer maps them to HTTP codes (app/shared/api/errors.py)."""


class DomainError(Exception):
    """Business rule violated (-> 422)."""


class NotFound(DomainError):
    """Entity missing OR outside the caller's merchant scope (-> 404, never reveals existence)."""


class Forbidden(DomainError):
    """Authenticated but not allowed (-> 403)."""


class InvalidCredentials(DomainError):
    """Login failed. Message is deliberately generic (-> 401)."""

    def __init__(self) -> None:
        super().__init__("Invalid email or password")


class InvalidStateTransition(DomainError):
    """Aggregate state machine refused a transition (-> 409)."""


class RateLimited(DomainError):
    """Too many attempts (-> 429). ``retry_after`` is in whole seconds."""

    def __init__(self, retry_after: int) -> None:
        self.retry_after = max(1, int(retry_after))
        super().__init__("Too many attempts; try again later")
