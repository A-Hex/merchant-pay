from datetime import date, datetime

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel

from app.container import get_get_transaction, get_scope, get_search_transactions
from app.contexts.ledger.application.ports import PageRequest, TransactionFilter
from app.contexts.ledger.application.queries import GetTransaction, SearchTransactions
from app.contexts.ledger.domain.transaction import Transaction
from app.shared.api.schemas import MoneyOut
from app.shared.domain.date_range import DateRange
from app.shared.domain.enums import Channel, DataOrigin, TransactionStatus
from app.shared.domain.merchant_scope import MerchantScope

router = APIRouter(prefix="/transactions", tags=["ledger"])


class TransactionOut(BaseModel):
    transaction_id: str
    merchant_id: str
    occurred_at: datetime
    amount: MoneyOut
    channel: Channel
    status: TransactionStatus
    category: str
    data_origin: DataOrigin
    source_batch_id: str | None

    @classmethod
    def of(cls, t: Transaction) -> "TransactionOut":
        return cls(transaction_id=t.transaction_id, merchant_id=t.merchant_id,
                   occurred_at=t.occurred_at, amount=MoneyOut.of(t.amount), channel=t.channel,
                   status=t.status, category=t.category, data_origin=t.data_origin,
                   source_batch_id=t.source_batch_id)


class TransactionPageOut(BaseModel):
    items: list[TransactionOut]
    total: int
    page: int
    size: int


@router.get("", response_model=TransactionPageOut)
def search_transactions(
    date_from: date | None = None,
    date_to: date | None = None,
    status: list[TransactionStatus] = Query(default=[]),
    channel: list[Channel] = Query(default=[]),
    q: str | None = Query(default=None, max_length=64),
    page: int = Query(default=1, ge=1),
    size: int = Query(default=25, ge=1, le=100),
    scope: MerchantScope = Depends(get_scope),
    uc: SearchTransactions = Depends(get_search_transactions),
) -> TransactionPageOut:
    period = None
    if date_from or date_to:
        period = DateRange.inclusive(date_from or date(2000, 1, 1), date_to or date(2100, 1, 1))
    result = uc.execute(scope, TransactionFilter(period, tuple(status), tuple(channel), q),
                        PageRequest(page, size))
    return TransactionPageOut(items=[TransactionOut.of(t) for t in result.items],
                              total=result.total, page=result.page, size=result.size)


@router.get("/{transaction_id}", response_model=TransactionOut)
def get_transaction(transaction_id: str, scope: MerchantScope = Depends(get_scope),
                    uc: GetTransaction = Depends(get_get_transaction)) -> TransactionOut:
    return TransactionOut.of(uc.execute(scope, transaction_id))
