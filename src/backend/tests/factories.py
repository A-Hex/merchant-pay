from datetime import datetime

from app.contexts.ledger.domain.transaction import Transaction
from app.shared.domain.enums import Channel, TransactionStatus
from app.shared.domain.money import Money


def tx(tid: str, status: TransactionStatus, amount: str, when: str = "2026-11-10 10:00",
       channel: Channel = Channel.POS, merchant: str = "M1") -> Transaction:
    return Transaction(tid, merchant, datetime.fromisoformat(when), Money.of(amount), channel,
                       status, "Retail")


A, D, C, R = (TransactionStatus.ACCEPTED, TransactionStatus.DECLINED,
              TransactionStatus.CANCELLED, TransactionStatus.REFUNDED)
