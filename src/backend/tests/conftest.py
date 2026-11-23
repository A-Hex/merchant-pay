from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.container import get_db, get_password_hasher, get_today
from app.contexts.ledger.application.import_transactions import ImportTransactions
from app.contexts.ledger.infrastructure.sql_transaction_repository import (
    SqlMerchantRegistry,
    SqlTransactionRepository,
)
from app.db.base import Base
from app.main import create_app
from app.seed.accounts import ensure_merchant, ensure_user
from app.shared.domain.enums import DataOrigin

FROZEN_TODAY = date(2026, 11, 20)


def _row(tid, merchant, when, amount, status, channel="TPE / POS"):
    return {"transaction_id": tid, "merchant_id": merchant, "occurred_at": when,
            "amount": amount, "channel": channel, "status": status, "category": "Retail"}


FIXTURE_ROWS = [
    _row("T1", "M1", "2026-11-18 10:00:00", "1000.00", "Accepted"),
    _row("T2", "M1", "2026-11-18 11:00:00", "2500.50", "Accepted", "E-commerce"),
    _row("T3", "M1", "2026-11-19 09:30:00", "700.00", "Declined", "E-commerce"),
    _row("T4", "M1", "2026-11-19 12:00:00", "300.00", "Cancelled"),
    _row("T5", "M1", "2026-11-19 15:00:00", "450.00", "Refunded"),
    _row("T6", "M1", "2026-10-25 10:00:00", "5000.00", "Accepted"),
    _row("X1", "M2", "2026-11-18 10:00:00", "99999.00", "Accepted"),  # other tenant
]


@pytest.fixture
def engine():
    eng = create_engine("sqlite+pysqlite:///:memory:", connect_args={"check_same_thread": False},
                        poolclass=StaticPool)
    Base.metadata.create_all(eng)
    yield eng
    eng.dispose()


@pytest.fixture
def seeded(engine):
    with Session(engine) as s, s.begin():
        ensure_merchant(s, "M1", "Merchant One", "Retail")
        ensure_merchant(s, "M2", "Merchant Two", "Retail")
        report = ImportTransactions(SqlTransactionRepository(s), SqlMerchantRegistry(s)).execute(
            enumerate(FIXTURE_ROWS, start=2), source_name="fixture",
            data_origin=DataOrigin.CHALLENGE_SOURCE)
        assert report.ok, report.errors
        hasher = get_password_hasher()
        ensure_user(s, hasher, "one@test.dz", "pw-one", "M1")
        ensure_user(s, hasher, "two@test.dz", "pw-two", "M2")
    return engine


@pytest.fixture
def client(seeded):
    app = create_app()
    factory = sessionmaker(bind=seeded, expire_on_commit=False)

    def override_db():
        s = factory()
        try:
            yield s
            s.commit()
        except Exception:
            s.rollback()
            raise
        finally:
            s.close()

    app.dependency_overrides[get_db] = override_db
    app.dependency_overrides[get_today] = lambda: FROZEN_TODAY
    with TestClient(app) as c:
        yield c


@pytest.fixture
def login(client):
    def _login(email="one@test.dz", password="pw-one"):
        r = client.post("/api/v1/auth/login", json={"email": email, "password": password})
        assert r.status_code == 204, r.text
        return client
    return _login
