"""Generate a merchant's Collections Summary. Scope comes from the server; nothing is cached."""

from __future__ import annotations

from datetime import datetime
from typing import Protocol

from app.contexts.identity.domain.model import Merchant
from app.contexts.ledger.domain.transaction import Transaction
from app.contexts.reports.domain.summary import CollectionsReport, build_report, validate_period
from app.shared.domain.date_range import DateRange
from app.shared.domain.errors import NotFound
from app.shared.domain.merchant_scope import MerchantScope


class TransactionReader(Protocol):
    def list_in_period(self, scope: MerchantScope, period: DateRange) -> list[Transaction]: ...


class MerchantReader(Protocol):
    def get(self, merchant_id: str) -> Merchant | None: ...


class AuditLog(Protocol):
    def record(self, actor_id: int, action: str, entity_ref: str) -> None: ...


class GenerateCollectionsReport:
    def __init__(self, reader: TransactionReader, merchants: MerchantReader, audit: AuditLog) -> None:
        self._reader, self._merchants, self._audit = reader, merchants, audit

    def execute(
        self, scope: MerchantScope, period: DateRange, now: datetime, export_format: str | None = None
    ) -> CollectionsReport:
        validate_period(period)
        merchant = self._merchants.get(scope.merchant_id)
        if merchant is None:
            raise NotFound("Merchant not found")
        report = build_report(
            merchant.merchant_id,
            merchant.display_name,
            period,
            self._reader.list_in_period(scope, period),
            self._reader.list_in_period(scope, period.previous()),
            now,
        )
        if export_format:  # audit the export itself, never its figures
            self._audit.record(
                scope.user_id,
                "report.exported",
                f"merchant:{scope.merchant_id} report:collections format:{export_format} "
                f"period:{period.start}..{period.last_day}",
            )
        return report
