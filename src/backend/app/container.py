"""Composition root: the ONLY module that knows concrete implementations.

Routers depend on these providers via FastAPI Depends(). Tests swap any of them with
app.dependency_overrides[provider] = lambda: Fake(...).
"""

from collections.abc import Iterator
from datetime import date, datetime
from functools import lru_cache
from zoneinfo import ZoneInfo

from fastapi import Depends, Header, HTTPException, Request, status
from sqlalchemy.orm import Session, sessionmaker

from app.config import Settings, get_settings
from app.contexts.analytics.application.get_dashboard import GetDashboard
from app.contexts.identity.application.use_cases import Authenticate, GetMe, ResolveScope
from app.contexts.identity.infrastructure.security import Argon2PasswordHasher, JwtTokenService
from app.contexts.identity.infrastructure.sql_repositories import (
    SqlAccessRepository,
    SqlMerchantRepository,
    SqlUserRepository,
)
from app.contexts.ledger.application.queries import GetTransaction, SearchTransactions
from app.contexts.ledger.infrastructure.sql_transaction_repository import SqlTransactionRepository
from app.db.session import make_engine, make_session_factory
from app.shared.domain.merchant_scope import MerchantScope

SESSION_COOKIE = "mp_session"


# ---- infrastructure --------------------------------------------------------
@lru_cache
def _session_factory() -> sessionmaker:
    return make_session_factory(make_engine(get_settings().database_url))


def get_db() -> Iterator[Session]:
    """One session (= one unit of work) per request; commit on success."""
    session = _session_factory()()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_today(settings: Settings = Depends(get_settings)) -> date:
    """Injectable clock: override in tests/demo to freeze 'today'."""
    return datetime.now(ZoneInfo(settings.timezone)).date()


@lru_cache
def get_password_hasher() -> Argon2PasswordHasher:
    return Argon2PasswordHasher()


def get_token_service(settings: Settings = Depends(get_settings)) -> JwtTokenService:
    return JwtTokenService(settings.jwt_secret, settings.jwt_ttl_minutes)


# ---- identity ----------------------------------------------------------------
def get_authenticate(db: Session = Depends(get_db), hasher=Depends(get_password_hasher),
                     tokens=Depends(get_token_service)) -> Authenticate:
    return Authenticate(SqlUserRepository(db), hasher, tokens)


def get_current_user_id(request: Request, tokens=Depends(get_token_service)) -> int:
    token = request.cookies.get(SESSION_COOKIE)
    user_id = tokens.decode(token) if token else None
    if user_id is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Not authenticated")
    return user_id


def get_scope(
    user_id: int = Depends(get_current_user_id),
    x_merchant_id: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> MerchantScope:
    """Tenant isolation entry point. Use Depends(get_scope) on EVERY merchant endpoint."""
    return ResolveScope(SqlAccessRepository(db)).execute(user_id, x_merchant_id)


def get_me_uc(db: Session = Depends(get_db)) -> GetMe:
    return GetMe(SqlUserRepository(db), SqlAccessRepository(db), SqlMerchantRepository(db))


# ---- ledger -------------------------------------------------------------------
def get_transaction_repository(db: Session = Depends(get_db)) -> SqlTransactionRepository:
    return SqlTransactionRepository(db)


def get_search_transactions(repo=Depends(get_transaction_repository)) -> SearchTransactions:
    return SearchTransactions(repo)


def get_get_transaction(repo=Depends(get_transaction_repository)) -> GetTransaction:
    return GetTransaction(repo)


# ---- analytics ----------------------------------------------------------------
def get_dashboard_uc(repo=Depends(get_transaction_repository)) -> GetDashboard:
    # analytics.TransactionReader port <- ledger SQL adapter
    return GetDashboard(repo)


# TODO: alerts / simulation providers go here (same pattern).
