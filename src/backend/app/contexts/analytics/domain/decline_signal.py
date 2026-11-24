"""Decline-rate estimate with an honest uncertainty band (no black box).

Model: each authorisation attempt is a Bernoulli trial (declined / accepted). With a
Jeffreys prior ``Beta(1/2, 1/2)`` the posterior is ``Beta(1/2 + declined, 1/2 + accepted)``.
The reported interval is the exact equal-tailed credible interval obtained by inverting
the regularized incomplete beta function, so it is valid for small samples where a
normal approximation is misleading.

This is deliberately *not* machine learning: the data has no labels, no features and
~150 rows, so a classifier would be unvalidated noise. The interval is the product.
"""

from __future__ import annotations

import math
from collections.abc import Iterable
from dataclasses import dataclass
from decimal import Decimal

from app.contexts.ledger.domain.transaction import Transaction
from app.shared.domain.enums import TransactionStatus
from app.shared.domain.rate import Rate

METHOD = (
    "Beta-Binomial / Jeffreys prior Beta(0.5, 0.5); exact equal-tailed credible "
    "interval from the regularized incomplete beta function"
)
LIMITATIONS = (
    "Observed authorisation outcomes only. No causal claim, no issuer breakdown and no "
    "fraud label: a high decline rate is a prompt to investigate, not proof of fraud. "
    "Small samples are dominated by the prior, so read the interval, not the point estimate."
)

_QUANT = Decimal("0.000001")


@dataclass(frozen=True, slots=True)
class CredibleInterval:
    lower: Decimal | None
    upper: Decimal | None
    level: Decimal


@dataclass(frozen=True, slots=True)
class DeclineSignal:
    accepted: int
    declined: int
    attempts: int
    observed_rate: Rate
    posterior_mean: Decimal | None
    interval: CredibleInterval
    prior_alpha: Decimal
    prior_beta: Decimal
    min_attempts: int
    sample_gate_met: bool
    method: str = METHOD
    limitations: str = LIMITATIONS


def _betacf(a: float, b: float, x: float) -> float:
    """Continued fraction for the incomplete beta function (Lentz's method)."""
    max_iter, eps, fpmin = 200, 3e-14, 1e-300
    qab, qap, qam = a + b, a + 1.0, a - 1.0
    c = 1.0
    d = 1.0 - qab * x / qap
    if abs(d) < fpmin:
        d = fpmin
    d = 1.0 / d
    h = d
    for m in range(1, max_iter + 1):
        m2 = 2 * m
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1.0 + aa * d
        d = fpmin if abs(d) < fpmin else d
        c = 1.0 + aa / c
        c = fpmin if abs(c) < fpmin else c
        d = 1.0 / d
        h *= d * c

        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1.0 + aa * d
        d = fpmin if abs(d) < fpmin else d
        c = 1.0 + aa / c
        c = fpmin if abs(c) < fpmin else c
        d = 1.0 / d
        delta = d * c
        h *= delta
        if abs(delta - 1.0) < eps:
            break
    return h


def regularized_incomplete_beta(a: float, b: float, x: float) -> float:
    """I_x(a, b), the CDF of Beta(a, b) at x."""
    if x <= 0.0:
        return 0.0
    if x >= 1.0:
        return 1.0
    log_front = (
        math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b)
        + a * math.log(x) + b * math.log1p(-x)
    )
    front = math.exp(log_front)
    if x < (a + 1.0) / (a + b + 2.0):
        return front * _betacf(a, b, x) / a
    return 1.0 - front * _betacf(b, a, 1.0 - x) / b


def beta_quantile(p: float, a: float, b: float, *, iterations: int = 120) -> float:
    """Inverse CDF of Beta(a, b) by bisection (monotone, deterministic, no SciPy)."""
    if not 0.0 <= p <= 1.0:
        raise ValueError("p must be within [0, 1]")
    if p == 0.0:
        return 0.0
    if p == 1.0:
        return 1.0
    lo, hi = 0.0, 1.0
    for _ in range(iterations):
        mid = (lo + hi) / 2.0
        if regularized_incomplete_beta(a, b, mid) < p:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2.0


def _q(value: float) -> Decimal:
    return Decimal(value).quantize(_QUANT)


def compute_decline_signal(transactions: Iterable[Transaction], *, min_attempts: int = 20,
                           confidence: Decimal = Decimal("0.90")) -> DeclineSignal:
    """Estimate the decline rate with a credible interval and a minimum-sample gate."""
    if not (Decimal(0) < confidence < Decimal(1)):
        raise ValueError("confidence must be between 0 and 1 exclusive")

    accepted = declined = 0
    for t in transactions:
        if t.status is TransactionStatus.ACCEPTED:
            accepted += 1
        elif t.status is TransactionStatus.DECLINED:
            declined += 1

    attempts = accepted + declined
    alpha_prior = beta_prior = Decimal("0.5")
    interval = CredibleInterval(None, None, confidence)
    posterior_mean: Decimal | None = None

    if attempts:
        a = float(alpha_prior) + declined
        b = float(beta_prior) + accepted
        tail = float((1 - confidence) / 2)
        interval = CredibleInterval(
            lower=_q(beta_quantile(tail, a, b)),
            upper=_q(beta_quantile(1 - tail, a, b)),
            level=confidence,
        )
        posterior_mean = _q(a / (a + b))

    return DeclineSignal(
        accepted=accepted,
        declined=declined,
        attempts=attempts,
        observed_rate=Rate(declined, attempts),
        posterior_mean=posterior_mean,
        interval=interval,
        prior_alpha=alpha_prior,
        prior_beta=beta_prior,
        min_attempts=min_attempts,
        sample_gate_met=attempts >= min_attempts,
    )
