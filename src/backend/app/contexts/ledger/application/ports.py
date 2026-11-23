"""Ports (interfaces) the ledger application needs. Implemented in infrastructure/."""

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Protocol

from app.contexts.ledger.domain.import_batch import ImportBatch
from app.contexts.ledger.domain.transaction import Transaction
from app.shared.domain.date_range import DateRange
from app.shared.domain.enums import Channel, TransactionStatus
from app.shared.domain.merchant_scope import MerchantScope


@dataclass(frozen=True, slots=True)
class TransactionFilter:
    period: DateRange | None = None
    statuses: tuple[TransactionStatus, ...] = ()
    channels: tuple[Channel, ...] = ()
    query: str | None = None  # transaction id contains


@dataclass(frozen=True, slots=True)
class PageRequest:
    number: int = 1
    size: int = 25


@dataclass(frozen=True, slots=True)
class TransactionPage:
    items: list[Transaction] = field(default_factory=list)
    total: int = 0
    page: int = 1
    size: int = 25


class TransactionRepository(Protocol):
    def search(self, scope: MerchantScope, flt: TransactionFilter,
               page: PageRequest) -> TransactionPage: ...

    def get(self, scope: MerchantScope, transaction_id: str) -> Transaction | None: ...


class TransactionWriter(Protocol):
    def existing_ids(self, ids: Iterable[str]) -> set[str]: ...

    def save_batch(self, batch: ImportBatch, transactions: Sequence[Transaction]) -> None: ...


class MerchantRegistry(Protocol):
    def ensure_exists(self, categories_by_merchant: Mapping[str, str]) -> None: ...
