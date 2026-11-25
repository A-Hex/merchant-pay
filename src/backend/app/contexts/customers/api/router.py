"""Customer loyalty & win-back API. Every endpoint is merchant-scoped by the server (get_scope)."""

from datetime import date, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query
from pydantic import BaseModel, ConfigDict

from app.container import (
    get_customer_detail_uc,
    get_customer_overview_uc,
    get_list_customers_uc,
    get_record_decision_uc,
    get_reengagement_uc,
    get_scope,
    get_today,
)
from app.contexts.customers.application.use_cases import (
    MAX_WINDOW_DAYS,
    MIN_WINDOW_DAYS,
    GetCustomer,
    GetCustomerOverview,
    GetReengagement,
    ListCustomers,
    RecordDecision,
)
from app.contexts.customers.domain.profiles import (
    Availability,
    CustomerBook,
    CustomerProfile,
    GroupTotal,
    Segment,
)
from app.contexts.customers.domain.reengagement import (
    RULE_VERSION,
    Decision,
    MerchantDecision,
    Suggestion,
)
from app.contexts.customers.domain.winback import BaselineSource, ReturnEvidence, ReturnStatus
from app.shared.api.schemas import MoneyOut, PeriodOut, RateOut, period_from_query
from app.shared.domain.enums import Channel, TransactionStatus
from app.shared.domain.merchant_scope import MerchantScope
from app.shared.domain.rate import Rate

router = APIRouter(prefix="/customers", tags=["customers"])

Token = Annotated[str, Path(pattern=r"^[A-Za-z0-9_-]{8,64}$")]
WindowDays = Annotated[int, Query(ge=MIN_WINDOW_DAYS, le=MAX_WINDOW_DAYS)]


# ---- shared shapes ---------------------------------------------------------------------------
class BaselineOut(BaseModel):
    source: BaselineSource
    median_days: float
    spread_days: float  # 1.4826 x MAD
    intervals: int


class ThresholdsOut(BaseModel):
    watch_days: float
    at_risk_days: float
    lapsed_days: float


class EvidenceOut(BaseModel):
    status: ReturnStatus
    last_purchase: date
    gap_days: int
    purchase_days: int
    baseline: BaselineOut | None
    thresholds: ThresholdsOut | None
    ratio: float | None
    rule_version: str

    @classmethod
    def of(cls, e: ReturnEvidence) -> "EvidenceOut":
        b, t = e.baseline, e.thresholds
        return cls(status=e.status, last_purchase=e.last_purchase, gap_days=e.gap_days,
                   purchase_days=e.purchase_days, ratio=e.ratio, rule_version=e.rule_version,
                   baseline=BaselineOut(source=b.source, median_days=b.median_days,
                                        spread_days=b.spread_days, intervals=b.intervals) if b else None,
                   thresholds=ThresholdsOut(watch_days=t.watch_days, at_risk_days=t.at_risk_days,
                                            lapsed_days=t.lapsed_days) if t else None)


class ProfileOut(BaseModel):
    token: str  # for this merchant's authorised view only; display `alias`
    alias: str
    first_purchase: date
    last_purchase: date
    lifetime_purchases: int
    recency_days: int
    frequency: int
    monetary: MoneyOut  # historical accepted value in the window
    segment: Segment
    high_value: bool | None
    evidence: EvidenceOut

    @classmethod
    def of(cls, p: CustomerProfile) -> "ProfileOut":
        return cls(token=p.token, alias=p.alias, first_purchase=p.first_purchase,
                   last_purchase=p.last_purchase, lifetime_purchases=p.lifetime_purchases,
                   recency_days=p.recency_days, frequency=p.frequency, monetary=MoneyOut.of(p.monetary),
                   segment=p.segment, high_value=p.high_value, evidence=EvidenceOut.of(p.evidence))


class RulesOut(BaseModel):
    segments_version: str
    window_days: int
    new_days: int
    loyal_min_tx: int
    loyal_min_span_days: int
    high_value_quantile: float
    min_customers: int
    winback_version: str
    min_personal_intervals: int
    min_pooled_intervals: int
    watch_ratio: float
    at_risk_ratio: float
    lapsed_ratio: float
    k_watch: float
    k_risk: float
    watch_min_days: int
    at_risk_min_days: int
    lapsed_min_days: int


class CoverageOut(BaseModel):
    accepted_in_window: int
    tokenised_in_window: int
    share: RateOut  # tokenised / accepted transactions in the window
    accepted_value_in_window: MoneyOut
    tokenised_value_in_window: MoneyOut


class BookOut(BaseModel):
    """Context every customer response carries: window, coverage, rules, availability."""

    as_of: date
    window: PeriodOut
    availability: Availability
    eligible_customers: int
    coverage: CoverageOut
    pooled_baseline: BaselineOut | None
    high_value_threshold: MoneyOut | None
    rules: RulesOut

    @classmethod
    def of(cls, b: CustomerBook) -> "BookOut":
        r, w, c, pb = b.rules, b.winback_rules, b.coverage, b.pooled_baseline
        return cls(
            as_of=b.as_of, window=PeriodOut.of(b.window), availability=b.availability,
            eligible_customers=len(b.profiles),
            coverage=CoverageOut(accepted_in_window=c.accepted_in_window,
                                 tokenised_in_window=c.tokenised_in_window, share=RateOut.of(c.share),
                                 accepted_value_in_window=MoneyOut.of(c.accepted_value_in_window),
                                 tokenised_value_in_window=MoneyOut.of(c.tokenised_value_in_window)),
            pooled_baseline=BaselineOut(source=pb.source, median_days=pb.median_days,
                                        spread_days=pb.spread_days, intervals=pb.intervals) if pb else None,
            high_value_threshold=MoneyOut.of(b.high_value_threshold) if b.high_value_threshold else None,
            rules=RulesOut(
                segments_version=r.version, window_days=r.window_days, new_days=r.new_days,
                loyal_min_tx=r.loyal_min_tx, loyal_min_span_days=r.loyal_min_span_days,
                high_value_quantile=float(r.high_value_quantile), min_customers=r.min_customers,
                winback_version=w.version, min_personal_intervals=w.min_personal_intervals,
                min_pooled_intervals=w.min_pooled_intervals, watch_ratio=w.watch_ratio,
                at_risk_ratio=w.at_risk_ratio, lapsed_ratio=w.lapsed_ratio, k_watch=w.k_watch,
                k_risk=w.k_risk, watch_min_days=w.watch_min_days, at_risk_min_days=w.at_risk_min_days,
                lapsed_min_days=w.lapsed_min_days),
        )


class GroupOut(BaseModel):
    customers: int
    transactions: int
    accepted_value: MoneyOut  # historical accepted value, not future revenue

    @classmethod
    def of(cls, g: GroupTotal) -> "GroupOut":
        return cls(customers=g.customers, transactions=g.transactions,
                   accepted_value=MoneyOut.of(g.accepted_value))


class DecisionOut(BaseModel):
    decision: Decision
    snooze_until: date | None
    decided_at: datetime

    @classmethod
    def of(cls, d: MerchantDecision | None) -> "DecisionOut | None":
        return cls(decision=d.decision, snooze_until=d.snooze_until, decided_at=d.decided_at) if d else None


# ---- overview --------------------------------------------------------------------------------
class SegmentRowOut(GroupOut):
    segment: Segment
    value_share: RateOut  # segment accepted value / all tokenised accepted value in the window


class StatusRowOut(GroupOut):
    status: ReturnStatus


class MonthOut(BaseModel):
    month_start: date
    complete: bool
    active: int
    new: int
    returning: int


class NewVsReturningOut(BaseModel):
    period: PeriodOut
    new: GroupOut
    returning: GroupOut


class OverviewOut(BaseModel):
    book: BookOut
    repeat_rate: RateOut  # customers with >= 2 accepted tx in the window / eligible customers
    segments: list[SegmentRowOut]
    statuses: list[StatusRowOut]
    new_vs_returning: NewVsReturningOut
    monthly: list[MonthOut]


@router.get("/overview", response_model=OverviewOut)
def overview(
    window_days: WindowDays = 180,
    date_from: date | None = None,
    date_to: date | None = None,
    scope: MerchantScope = Depends(get_scope),
    today: date = Depends(get_today),
    uc: GetCustomerOverview = Depends(get_customer_overview_uc),
) -> OverviewOut:
    o = uc.execute(scope, today, window_days, period_from_query(date_from, date_to, today))
    nv = o.new_vs_returning
    return OverviewOut(
        book=BookOut.of(o.book), repeat_rate=RateOut.of(o.repeat_rate),
        segments=[SegmentRowOut(segment=s, **GroupOut.of(g).model_dump(), value_share=RateOut.of(Rate(
            g.accepted_value.centimes, o.book.coverage.tokenised_value_in_window.centimes)))
            for s, g in o.segments.items()],
        statuses=[StatusRowOut(status=s, **GroupOut.of(g).model_dump()) for s, g in o.statuses.items()],
        new_vs_returning=NewVsReturningOut(period=PeriodOut.of(nv.period), new=GroupOut.of(nv.new),
                                           returning=GroupOut.of(nv.returning)),
        monthly=[MonthOut(month_start=m.month_start, complete=m.complete, active=m.active, new=m.new,
                          returning=m.returning) for m in o.monthly],
    )


# ---- re-engagement (win-back radar) ------------------------------------------------------------
class ReengageEntryOut(BaseModel):
    customer: ProfileOut
    suggestion: Suggestion
    recheck_on: date | None
    decision: DecisionOut | None
    hidden: bool


class ReengagementOut(BaseModel):
    book: BookOut
    rule_version: str
    entries: list[ReengageEntryOut]
    hidden_count: int


@router.get("/reengagement", response_model=ReengagementOut)
def reengagement(
    window_days: WindowDays = 180,
    include_hidden: bool = False,
    scope: MerchantScope = Depends(get_scope),
    today: date = Depends(get_today),
    uc: GetReengagement = Depends(get_reengagement_uc),
) -> ReengagementOut:
    r = uc.execute(scope, today, window_days, include_hidden)
    return ReengagementOut(
        book=BookOut.of(r.book), rule_version=RULE_VERSION, hidden_count=r.hidden_count,
        entries=[ReengageEntryOut(customer=ProfileOut.of(e.profile), suggestion=e.suggestion,
                                  recheck_on=e.recheck_on, decision=DecisionOut.of(e.decision),
                                  hidden=e.hidden) for e in r.entries],
    )


# ---- list and detail -------------------------------------------------------------------------
class CustomerPageOut(BaseModel):
    book: BookOut
    items: list[ProfileOut]
    total: int
    page: int
    size: int


@router.get("", response_model=CustomerPageOut)
def list_customers(
    window_days: WindowDays = 180,
    segment: Segment | None = None,
    status: ReturnStatus | None = None,
    high_value: bool | None = None,
    page: Annotated[int, Query(ge=1)] = 1,
    size: Annotated[int, Query(ge=1, le=100)] = 25,
    scope: MerchantScope = Depends(get_scope),
    today: date = Depends(get_today),
    uc: ListCustomers = Depends(get_list_customers_uc),
) -> CustomerPageOut:
    p = uc.execute(scope, today, window_days, segment=segment, status=status, high_value=high_value,
                   page=page, size=size)
    return CustomerPageOut(book=BookOut.of(p.book), items=[ProfileOut.of(x) for x in p.items],
                           total=p.total, page=p.page, size=p.size)


class CustomerTxOut(BaseModel):
    transaction_id: str
    occurred_at: datetime
    amount: MoneyOut
    channel: Channel
    status: TransactionStatus


class StatusCountOut(BaseModel):
    status: TransactionStatus
    count: int
    amount: MoneyOut


class CustomerDetailOut(BaseModel):
    book: BookOut
    customer: ProfileOut
    statuses: list[StatusCountOut]  # all statuses for this customer, all history
    recent: list[CustomerTxOut]
    decision: DecisionOut | None


@router.get("/{token}", response_model=CustomerDetailOut)
def customer_detail(
    token: Token,
    window_days: WindowDays = 180,
    scope: MerchantScope = Depends(get_scope),
    today: date = Depends(get_today),
    uc: GetCustomer = Depends(get_customer_detail_uc),
) -> CustomerDetailOut:
    d = uc.execute(scope, today, window_days, token)
    return CustomerDetailOut(
        book=BookOut.of(d.book), customer=ProfileOut.of(d.profile), decision=DecisionOut.of(d.decision),
        statuses=[StatusCountOut(status=s.status, count=s.count, amount=MoneyOut.of(s.amount))
                  for s in d.statuses],
        recent=[CustomerTxOut(transaction_id=t.transaction_id, occurred_at=t.occurred_at,
                              amount=MoneyOut.of(t.amount), channel=t.channel, status=t.status)
                for t in d.recent],
    )


class DecisionIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    decision: Decision
    snooze_until: date | None = None


@router.post("/{token}/decisions", response_model=DecisionOut, status_code=201)
def record_decision(
    token: Token,
    body: DecisionIn,
    scope: MerchantScope = Depends(get_scope),
    today: date = Depends(get_today),
    uc: RecordDecision = Depends(get_record_decision_uc),
) -> DecisionOut:
    return DecisionOut.of(uc.execute(scope, token, body.decision, body.snooze_until, today))
