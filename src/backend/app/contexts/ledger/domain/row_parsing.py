"""Pure validation of one source row (canonical keys) into a Transaction.

Infrastructure readers (xlsx/csv) are responsible only for mapping headers to these keys.
"""

from collections.abc import Mapping
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

from app.contexts.ledger.domain.import_batch import RowError
from app.contexts.ledger.domain.transaction import Transaction
from app.shared.domain.enums import Channel, DataOrigin, TransactionStatus
from app.shared.domain.money import Money

REQUIRED_FIELDS = (
    "transaction_id", "merchant_id", "occurred_at", "amount", "channel", "status", "category",
)
_MAX_AMOUNT = Decimal("100000000")  # sanity bound only; NOT a business ceiling
_DATETIME_FORMATS = (
    "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d",
    "%d/%m/%Y %H:%M:%S", "%d/%m/%Y %H:%M", "%d/%m/%Y",
)


def _parse_datetime(value: object) -> datetime:
    if isinstance(value, datetime):
        return value.replace(tzinfo=None)
    if isinstance(value, date):
        return datetime.combine(value, datetime.min.time())
    text = str(value).strip()
    for fmt in _DATETIME_FORMATS:
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    raise ValueError(f"Unrecognised date '{text}'")


def _parse_amount(value: object) -> Money:
    try:
        amount = Decimal(str(value).replace(" ", "").replace(",", "."))
    except InvalidOperation as exc:
        raise ValueError(f"Not a number: '{value}'") from exc
    if amount <= 0 or amount > _MAX_AMOUNT:
        raise ValueError(f"Amount out of range: {amount}")
    return Money.of(amount)


def parse_row(
    raw: Mapping[str, object], row_number: int, *, data_origin: DataOrigin
) -> tuple[Transaction | None, list[RowError]]:
    errors: list[RowError] = []
    for f in REQUIRED_FIELDS:
        if raw.get(f) is None or str(raw.get(f)).strip() == "":
            errors.append(RowError(row_number, f, "missing value"))
    if errors:
        return None, errors

    def attempt(field: str, fn):
        try:
            return fn(raw[field])
        except ValueError as exc:
            errors.append(RowError(row_number, field, str(exc)))
            return None

    occurred_at = attempt("occurred_at", _parse_datetime)
    amount = attempt("amount", _parse_amount)
    channel = attempt("channel", lambda v: Channel.parse(str(v)))
    status = attempt("status", lambda v: TransactionStatus.parse(str(v)))
    if errors:
        return None, errors

    return Transaction(
        transaction_id=str(raw["transaction_id"]).strip(),
        merchant_id=str(raw["merchant_id"]).strip(),
        occurred_at=occurred_at,
        amount=amount,
        channel=channel,
        status=status,
        category=str(raw["category"]).strip(),
        data_origin=data_origin,
    ), []
