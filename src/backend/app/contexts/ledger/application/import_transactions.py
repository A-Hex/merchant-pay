"""Use case: import source rows as one immutable, traceable batch (all-or-nothing)."""

import dataclasses
from collections.abc import Callable, Iterable, Mapping
from datetime import UTC, datetime
from uuid import uuid4

from app.contexts.ledger.application.ports import MerchantRegistry, TransactionWriter
from app.contexts.ledger.domain.import_batch import ImportBatch, ImportReport, RowError
from app.contexts.ledger.domain.row_parsing import parse_row
from app.contexts.ledger.domain.transaction import Transaction
from app.shared.domain.enums import DataOrigin


class ImportTransactions:
    def __init__(
        self,
        writer: TransactionWriter,
        merchants: MerchantRegistry,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
        id_factory: Callable[[], str] = lambda: uuid4().hex,
    ) -> None:
        self._writer = writer
        self._merchants = merchants
        self._clock = clock
        self._id_factory = id_factory

    def execute(
        self,
        rows: Iterable[tuple[int, Mapping[str, object]]],
        *,
        source_name: str,
        data_origin: DataOrigin,
    ) -> ImportReport:
        parsed: list[Transaction] = []
        errors: list[RowError] = []
        seen: dict[str, int] = {}

        for row_number, raw in rows:
            tx, row_errors = parse_row(raw, row_number, data_origin=data_origin)
            if row_errors:
                errors.extend(row_errors)
                continue
            if tx.transaction_id in seen:
                errors.append(RowError(row_number, "transaction_id",
                                       f"duplicate of row {seen[tx.transaction_id]}"))
                continue
            seen[tx.transaction_id] = row_number
            parsed.append(tx)

        for tid in self._writer.existing_ids(seen):
            errors.append(RowError(seen[tid], "transaction_id", f"'{tid}' already imported"))

        if errors:  # no partial silent corruption
            return ImportReport(source_name, None, 0, sorted(errors, key=lambda e: e.row_number))

        batch = ImportBatch(self._id_factory(), source_name, data_origin, self._clock(), len(parsed))
        parsed = [dataclasses.replace(t, source_batch_id=batch.batch_id) for t in parsed]
        self._merchants.ensure_exists({t.merchant_id: t.category for t in parsed})
        self._writer.save_batch(batch, parsed)
        return ImportReport(source_name, batch.batch_id, len(parsed))
