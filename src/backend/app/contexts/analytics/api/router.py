from datetime import date

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.container import get_dashboard_uc, get_scope, get_today
from app.contexts.analytics.application.get_dashboard import GetDashboard
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
