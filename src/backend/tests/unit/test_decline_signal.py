"""Statistical core: posterior maths, interval validity, sample gate, zero-data safety."""

from datetime import datetime
from decimal import Decimal

import pytest

from app.contexts.analytics.domain.decline_signal import (
    beta_quantile,
    compute_decline_signal,
    regularized_incomplete_beta,
)
from app.contexts.ledger.domain.transaction import Transaction
from app.shared.domain.enums import Channel, TransactionStatus
from app.shared.domain.money import Money


def _tx(tid: str, status: TransactionStatus) -> Transaction:
    return Transaction(tid, "M1", datetime(2026, 11, 10, 10, 0), Money(1000), Channel.POS,
                       status, "Retail")


def _attempts(accepted: int, declined: int) -> list[Transaction]:
    return ([_tx(f"A{i}", TransactionStatus.ACCEPTED) for i in range(accepted)]
            + [_tx(f"D{i}", TransactionStatus.DECLINED) for i in range(declined)])


def test_incomplete_beta_matches_known_values():
    # I_x(1, 1) = x  (uniform CDF)
    assert regularized_incomplete_beta(1, 1, 0.25) == pytest.approx(0.25, abs=1e-9)
    # Beta(2, 2) CDF is dominated by the continued fraction; median must be 0.5 by symmetry.
    assert beta_quantile(0.5, 2, 2) == pytest.approx(0.5, abs=1e-6)
    # Beta(1/2, 1/2) is the arcsine distribution: CDF at 0.5 is 0.5.
    assert regularized_incomplete_beta(0.5, 0.5, 0.5) == pytest.approx(0.5, abs=1e-9)


def test_quantiles_are_monotone_and_bounded():
    lo, hi = beta_quantile(0.05, 3.5, 8.5), beta_quantile(0.95, 3.5, 8.5)
    assert 0.0 < lo < hi < 1.0


def test_zero_attempts_is_undefined_not_zero_percent():
    signal = compute_decline_signal([])
    assert signal.attempts == 0
    assert signal.observed_rate.value is None  # never fabricate 0%
    assert signal.posterior_mean is None
    assert signal.interval.lower is None and signal.interval.upper is None
    assert signal.sample_gate_met is False


def test_posterior_mean_and_interval_contain_it():
    signal = compute_decline_signal(_attempts(accepted=80, declined=20))
    # Beta(0.5 + 20, 0.5 + 80) -> mean 20.5 / 101
    assert signal.posterior_mean == pytest.approx(Decimal("0.202970"), abs=Decimal("1e-6"))
    assert signal.interval.lower < signal.posterior_mean < signal.interval.upper
    assert 0 <= signal.interval.lower <= signal.interval.upper <= 1
    assert signal.interval.level == Decimal("0.90")
    assert signal.sample_gate_met is True


def test_non_authorisation_statuses_are_excluded():
    signal = compute_decline_signal(
        _attempts(accepted=1, declined=1)
        + [_tx("C1", TransactionStatus.CANCELLED), _tx("R1", TransactionStatus.REFUNDED)]
    )
    assert signal.attempts == 2 and signal.accepted == 1 and signal.declined == 1


def test_small_sample_is_flagged_by_the_gate():
    signal = compute_decline_signal(_attempts(accepted=2, declined=1), min_attempts=20)
    assert signal.attempts == 3
    assert signal.sample_gate_met is False
    assert signal.posterior_mean is not None  # still shown, but with a wide interval


def test_confidence_level_is_configurable():
    signal = compute_decline_signal(_attempts(accepted=10, declined=10),
                                    confidence=Decimal("0.5"))
    assert signal.interval.level == Decimal("0.5")
    assert signal.interval.lower < signal.interval.upper


def test_invalid_confidence_is_rejected():
    with pytest.raises(ValueError):
        compute_decline_signal(_attempts(1, 1), confidence=Decimal("1"))
