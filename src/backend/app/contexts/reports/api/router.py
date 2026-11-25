"""Reports & Sharing: merchant-scoped, aggregated Collections Summary (JSON preview, PDF, CSV)."""

from datetime import date, datetime
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel

from app.config import Settings, get_settings
from app.container import get_collections_report_uc, get_scope, get_today
from app.contexts.reports.application.use_cases import GenerateCollectionsReport
from app.contexts.reports.domain.csv_export import render_csv
from app.contexts.reports.domain.summary import CollectionsReport, safe_filename
from app.contexts.reports.infrastructure.pdf import render_pdf
from app.shared.api.schemas import MoneyOut, PeriodOut, RateOut, period_from_query
from app.shared.domain.enums import Channel, DataOrigin, TransactionStatus
from app.shared.domain.merchant_scope import MerchantScope

router = APIRouter(prefix="/reports", tags=["reports"])
NO_STORE = {"Cache-Control": "no-store, private"}


class ReportStatusOut(BaseModel):
    status: TransactionStatus
    count: int
    amount: MoneyOut
    previous_count: int
    previous_amount: MoneyOut


class ReportChannelOut(BaseModel):
    channel: Channel
    count: int
    count_share: RateOut
    accepted_amount: MoneyOut
    amount_share: RateOut


class ReportProvenanceOut(BaseModel):
    origin: DataOrigin
    transactions: int


class CollectionsReportOut(BaseModel):
    merchant_id: str
    merchant_name: str
    period: PeriodOut
    previous_period: PeriodOut
    generated_at: datetime
    currency: str = "DZD"
    synthetic: bool
    provenance: list[ReportProvenanceOut]
    gross_collected: MoneyOut
    collected_change_pct: float | None
    collected_change_kind: str
    accepted_count: int
    acceptance_rate: RateOut
    average_ticket: MoneyOut | None
    statuses: list[ReportStatusOut]
    channels: list[ReportChannelOut]
    pdf_filename: str
    csv_filename: str


def _now(settings: Settings, today: date) -> datetime:
    now = datetime.now(ZoneInfo(settings.timezone)).replace(tzinfo=None)
    return now.replace(year=today.year, month=today.month, day=today.day) if settings.demo_today else now


def _out(r: CollectionsReport) -> CollectionsReportOut:
    k, p = r.kpis, r.previous_kpis
    return CollectionsReportOut(
        merchant_id=r.merchant_id,
        merchant_name=r.merchant_name,
        period=PeriodOut.of(r.period),
        previous_period=PeriodOut.of(r.previous_period),
        generated_at=r.generated_at,
        synthetic=r.synthetic,
        provenance=[ReportProvenanceOut(origin=o, transactions=n) for o, n in sorted(r.provenance.items())],
        gross_collected=MoneyOut.of(k.gross_collected),
        collected_change_pct=float(r.collected_change.pct) if r.collected_change.pct is not None else None,
        collected_change_kind=r.collected_change.kind.value,
        accepted_count=k.accepted_count,
        acceptance_rate=RateOut.of(k.acceptance_rate),
        average_ticket=MoneyOut.of(k.average_ticket) if k.average_ticket else None,
        statuses=[
            ReportStatusOut(
                status=s,
                count=k.by_status[s].count,
                amount=MoneyOut.of(k.by_status[s].amount),
                previous_count=p.by_status[s].count,
                previous_amount=MoneyOut.of(p.by_status[s].amount),
            )
            for s in TransactionStatus
        ],
        channels=[
            ReportChannelOut(
                channel=c.channel,
                count=c.count,
                count_share=RateOut.of(c.count_share),
                accepted_amount=MoneyOut.of(c.accepted_amount),
                amount_share=RateOut.of(c.amount_share),
            )
            for c in r.channels
        ],
        pdf_filename=safe_filename(r.merchant_id, r.period, "pdf"),
        csv_filename=safe_filename(r.merchant_id, r.period, "csv"),
    )


@router.get("/collections-summary", response_model=CollectionsReportOut)
def preview(
    date_from: date | None = None,
    date_to: date | None = None,
    response: Response = None,
    scope: MerchantScope = Depends(get_scope),
    today: date = Depends(get_today),
    settings: Settings = Depends(get_settings),
    uc: GenerateCollectionsReport = Depends(get_collections_report_uc),
) -> CollectionsReportOut:
    response.headers.update(NO_STORE)
    return _out(uc.execute(scope, period_from_query(date_from, date_to, today), _now(settings, today)))


def _file(
    uc: GenerateCollectionsReport,
    scope: MerchantScope,
    date_from: date | None,
    date_to: date | None,
    today: date,
    settings: Settings,
    fmt: str,
) -> Response:
    r = uc.execute(scope, period_from_query(date_from, date_to, today), _now(settings, today), fmt)
    body, media = (
        (render_pdf(r), "application/pdf") if fmt == "pdf" else (render_csv(r), "text/csv; charset=utf-8")
    )
    name = safe_filename(r.merchant_id, r.period, fmt)
    return Response(
        body, media_type=media, headers={**NO_STORE, "Content-Disposition": f'attachment; filename="{name}"'}
    )


@router.get("/collections-summary.pdf", response_class=Response)
def pdf(
    date_from: date | None = None,
    date_to: date | None = None,
    scope: MerchantScope = Depends(get_scope),
    today: date = Depends(get_today),
    settings: Settings = Depends(get_settings),
    uc: GenerateCollectionsReport = Depends(get_collections_report_uc),
) -> Response:
    return _file(uc, scope, date_from, date_to, today, settings, "pdf")


@router.get("/collections-summary.csv", response_class=Response)
def csv(
    date_from: date | None = None,
    date_to: date | None = None,
    scope: MerchantScope = Depends(get_scope),
    today: date = Depends(get_today),
    settings: Settings = Depends(get_settings),
    uc: GenerateCollectionsReport = Depends(get_collections_report_uc),
) -> Response:
    return _file(uc, scope, date_from, date_to, today, settings, "csv")
