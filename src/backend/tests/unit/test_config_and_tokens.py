"""Fail-fast configuration and JWT claim binding."""

from datetime import UTC, datetime, timedelta

import jwt
import pytest

from app.config import Environment, Settings
from app.contexts.identity.infrastructure.security import Argon2PasswordHasher, JwtTokenService

_STRONG_SECRET = "x" * 48


def _settings(**over) -> Settings:
    base = dict(environment=Environment.PRODUCTION, jwt_secret=_STRONG_SECRET,
                cookie_secure=True, cors_origins=["https://app.example.dz"],
                _env_file=None)
    return Settings(**{**base, **over})


def test_production_rejects_the_default_secret():
    with pytest.raises(RuntimeError, match="JWT_SECRET"):
        Settings(environment=Environment.PRODUCTION, _env_file=None).validate_runtime()


def test_production_rejects_short_secret_insecure_cookie_and_http_origin():
    with pytest.raises(RuntimeError) as err:
        _settings(jwt_secret="short", cookie_secure=False,
                  cors_origins=["http://app.example.dz"]).validate_runtime()
    message = str(err.value)
    assert "32 characters" in message
    assert "COOKIE_SECURE" in message
    assert "https://" in message


def test_production_rejects_a_frozen_demo_clock():
    with pytest.raises(RuntimeError, match="DEMO_TODAY"):
        _settings(demo_today=datetime(2026, 11, 20).date()).validate_runtime()


def test_a_correct_production_configuration_is_accepted():
    _settings().validate_runtime()  # must not raise


def test_development_still_requires_a_minimum_secret_length():
    with pytest.raises(RuntimeError, match="16 characters"):
        Settings(jwt_secret="tooshort", _env_file=None).validate_runtime()


def test_samesite_none_requires_secure_cookie():
    with pytest.raises(RuntimeError, match="COOKIE_SAMESITE"):
        Settings(cookie_samesite="none", cookie_secure=False, _env_file=None).validate_runtime()


def test_real_argon2_hasher_round_trip():
    hasher = Argon2PasswordHasher()
    stored = hasher.hash("correct horse")
    assert stored != "correct horse"
    assert hasher.verify("correct horse", stored) is True
    assert hasher.verify("wrong horse", stored) is False
    assert hasher.verify("anything", "not-a-hash") is False


def _service() -> JwtTokenService:
    return JwtTokenService("s" * 40, 60, issuer="issuer-a", audience="audience-a")


def test_valid_token_round_trip():
    service = _service()
    assert service.decode(service.issue(42)) == 42


def test_token_for_another_audience_is_rejected():
    service = _service()
    other = JwtTokenService("s" * 40, 60, issuer="issuer-a", audience="audience-b")
    assert service.decode(other.issue(42)) is None


def test_token_for_another_issuer_is_rejected():
    service = _service()
    other = JwtTokenService("s" * 40, 60, issuer="issuer-b", audience="audience-a")
    assert service.decode(other.issue(42)) is None


def test_wrong_token_type_is_rejected():
    service = _service()
    assert service.decode(service.issue(42, token_type="refresh")) is None


def test_token_without_required_claims_is_rejected():
    now = datetime.now(UTC)
    legacy = jwt.encode({"sub": "1", "iat": now, "exp": now + timedelta(minutes=5)},
                        "s" * 40, algorithm="HS256")
    assert _service().decode(legacy) is None


def test_tampered_or_garbage_token_is_rejected():
    service = _service()
    assert service.decode("not-a-jwt") is None
    token = service.issue(1)
    assert service.decode(token[:-2] + "xx") is None
