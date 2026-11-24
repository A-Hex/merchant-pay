from datetime import date

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from app.container import (
    get_collections_summary,
    get_dashboard_uc,
    get_decline_signal,
    get_scope,
    get_today,
)
from app.contexts.analytics.application.get_collections import GetCollectionsSummary
from app.contexts.analytics.application.get_dashboard import GetDashboard
from app.contexts.analytics.application.get_decline_signal import GetDeclineSignal
from app.contexts.analytics.domain.decline_signal import DeclineSignal
from app.contexts.analytics.domain.kpis import Granularity, KpiSnapshot
from app.contexts.analytics.domain.period_comparison import ChangeKind, PeriodChange
from app.shared.api.schemas import MoneyOut, PeriodOut, RateOut, period_from_query
from app.shared.domain.enums import Channel, TransactionStatus
from app.shared.domain.merchant_scope import MerchantScope

router = APIRouter(prefix="/analytics", tags=["analytics"])


class StatusTotalOut(BaseModel):
    status: TransactionStatus
    count: int
    amount: MoneyOut


class KpiOut(BaseModel):
    total_count: int
    accepted_count: int
    gross_collected: MoneyOut
    average_ticket: MoneyOut | None
    acceptance_rate: RateOut
    decline_rate: RateOut
    refunded_amount: MoneyOut
    by_status: list[StatusTotalOut]

    @classmethod
    def of(cls, k: KpiSnapshot) -> "KpiOut":
        return cls(
            total_count=k.total_count, accepted_count=k.accepted_count,
            gross_collected=MoneyOut.of(k.gross_collected),
            average_ticket=MoneyOut.of(k.average_ticket) if k.average_ticket else None,
            acceptance_rate=RateOut.of(k.acceptance_rate), decline_rate=RateOut.of(k.decline_rate),
            refunded_amount=MoneyOut.of(k.refunded_amount),
            by_status=[StatusTotalOut(status=s.status, count=s.count, amount=MoneyOut.of(s.amount))
                       for s in k.by_status.values()],
        )


class ChangeOut(BaseModel):
    current: int
    previous: int
    delta: int
    pct: float | None
    kind: ChangeKind

    @classmethod
    def of(cls, c: PeriodChange) -> "ChangeOut":
        return cls(current=c.current, previous=c.previous, delta=c.delta,
                   pct=float(c.pct) if c.pct is not None else None, kind=c.kind)


class SeriesPointOut(BaseModel):
    bucket_start: date
    accepted_amount: MoneyOut
    accepted_count: int


class ChannelOut(BaseModel):
    channel: Channel
    count: int
    count_share: RateOut
    accepted_amount: MoneyOut
    amount_share: RateOut


class DashboardOut(BaseModel):
    period: PeriodOut
    previous_period: PeriodOut
    granularity: Granularity
    kpis: KpiOut
    previous_kpis: KpiOut
    collected_change: ChangeOut  # values in centimes
    accepted_count_change: ChangeOut  # values in counts
    series: list[SeriesPointOut]
    channels: list[ChannelOut]


@router.get("/dashboard", response_model=DashboardOut)
def dashboard(
    date_from: date | None = None,
    date_to: date | None = None,
    granularity: Granularity = Granularity.DAY,
    scope: MerchantScope = Depends(get_scope),
    today: date = Depends(get_today),
    uc: GetDashboard = Depends(get_dashboard_uc),
) -> DashboardOut:
    d = uc.execute(scope, period_from_query(date_from, date_to, today), granularity)
    return DashboardOut(
        period=PeriodOut.of(d.period),
        previous_period=PeriodOut.of(d.previous_period),
        granularity=granularity,
        kpis=KpiOut.of(d.kpis),
        previous_kpis=KpiOut.of(d.previous_kpis),
        collected_change=ChangeOut.of(d.collected_change),
        accepted_count_change=ChangeOut.of(d.accepted_count_change),
        series=[SeriesPointOut(bucket_start=p.bucket_start,
                               accepted_amount=MoneyOut.of(p.accepted_amount),
                               accepted_count=p.accepted_count) for p in d.series],
        channels=[ChannelOut(channel=c.channel, count=c.count, count_share=RateOut.of(c.count_share),
                             accepted_amount=MoneyOut.of(c.accepted_amount),
                             amount_share=RateOut.of(c.amount_share)) for c in d.channels],
    )


# ---- collections (module 03): status-separated totals, period A vs period B ------------
collections_router = APIRouter(prefix="/collections", tags=["collections"])


class StatusSummaryOut(BaseModel):
    status: TransactionStatus
    count_a: int
    count_b: int
    amount_a: MoneyOut
    amount_b: MoneyOut
    count_change: ChangeOut
    amount_change: ChangeOut


class CollectionsSummaryOut(BaseModel):
    period_a: PeriodOut
    period_b: PeriodOut
    total_count_a: int
    total_count_b: int
    total_count_change: ChangeOut
    collected_a: MoneyOut
    collected_b: MoneyOut
    collected_change: ChangeOut
    acceptance_rate_a: RateOut
    acceptance_rate_b: RateOut
    by_status: list[StatusSummaryOut]


@collections_router.get("/summary", response_model=CollectionsSummaryOut)
def collections_summary(
    a_from: date | None = None,
    a_to: date | None = None,
    b_from: date | None = None,
    b_to: date | None = None,
    scope: MerchantScope = Depends(get_scope),
    today: date = Depends(get_today),
    uc: GetCollectionsSummary = Depends(get_collections_summary),
) -> CollectionsSummaryOut:
    period_a = period_from_query(a_from, a_to, today)
    # B is optional: default to the like-for-like period immediately before A.
    period_b = period_from_query(b_from, b_to, today) if (b_from or b_to) else period_a.previous()
    s = uc.execute(scope, period_a, period_b)
    a, b = s.totals_a, s.totals_b
    return CollectionsSummaryOut(
        period_a=PeriodOut.of(s.period_a),
        period_b=PeriodOut.of(s.period_b),
        total_count_a=a.total_count,
        total_count_b=b.total_count,
        total_count_change=ChangeOut.of(s.total_count_change),
        collected_a=MoneyOut.of(a.gross_collected),
        collected_b=MoneyOut.of(b.gross_collected),
        collected_change=ChangeOut.of(s.collected_change),
        acceptance_rate_a=RateOut.of(a.acceptance_rate),
        acceptance_rate_b=RateOut.of(b.acceptance_rate),
        by_status=[
            StatusSummaryOut(status=c.status, count_a=c.a.count, count_b=c.b.count,
                             amount_a=MoneyOut.of(c.a.amount), amount_b=MoneyOut.of(c.b.amount),
                             count_change=ChangeOut.of(c.count_change),
                             amount_change=ChangeOut.of(c.amount_change))
            for c in s.by_status
        ],
    )


# ---- insights (module 04): decline rate with an explicit uncertainty band --------------
insights_router = APIRouter(prefix="/insights", tags=["insights"])


class CredibleIntervalOut(BaseModel):
    lower: float | None
    upper: float | None
    level: float


class PriorOut(BaseModel):
    alpha: float
    beta: float
    family: str = "Jeffreys Beta(0.5, 0.5)"


class DeclineSignalOut(BaseModel):
    accepted: int
    declined: int
    attempts: int
    observed_rate: RateOut
    posterior_mean: float | None  # display only, 0..1
    credible_interval: CredibleIntervalOut
    prior: PriorOut
    min_attempts: int
    sample_gate_met: bool
    method: str
    limitations: str

    @classmethod
    def of(cls, s: DeclineSignal) -> "DeclineSignalOut":
        return cls(
            accepted=s.accepted, declined=s.declined, attempts=s.attempts,
            observed_rate=RateOut.of(s.observed_rate),
            posterior_mean=float(s.posterior_mean) if s.posterior_mean is not None else None,
            credible_interval=CredibleIntervalOut(
                lower=float(s.interval.lower) if s.interval.lower is not None else None,
                upper=float(s.interval.upper) if s.interval.upper is not None else None,
                level=float(s.interval.level),
            ),
            prior=PriorOut(alpha=float(s.prior_alpha), beta=float(s.prior_beta)),
            min_attempts=s.min_attempts, sample_gate_met=s.sample_gate_met,
            method=s.method, limitations=s.limitations,
        )


class DeclineInsightOut(BaseModel):
    period: PeriodOut
    signal: DeclineSignalOut


@insights_router.get("/decline", response_model=DeclineInsightOut)
def decline_insight(
    date_from: date | None = None,
    date_to: date | None = None,
    min_attempts: int = Query(default=20, ge=1, le=10_000),
    scope: MerchantScope = Depends(get_scope),
    today: date = Depends(get_today),
    uc: GetDeclineSignal = Depends(get_decline_signal),
) -> DeclineInsightOut:
    insight = uc.execute(scope, period_from_query(date_from, date_to, today), min_attempts)
    return DeclineInsightOut(period=PeriodOut.of(insight.period),
                             signal=DeclineSignalOut.of(insight.signal))
