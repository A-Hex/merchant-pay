"""Read use cases for the transaction ledger."""

from app.contexts.ledger.application.ports import (
    PageRequest,
    TransactionFilter,
    TransactionPage,
    TransactionRepository,
)
from app.contexts.ledger.domain.transaction import Transaction
from app.shared.domain.errors import NotFound
from app.shared.domain.merchant_scope import MerchantScope


class SearchTransactions:
    def __init__(self, repo: TransactionRepository) -> None:
        self._repo = repo

    def execute(self, scope: MerchantScope, flt: TransactionFilter,
                page: PageRequest) -> TransactionPage:
        return self._repo.search(scope, flt, page)


class GetTransaction:
    def __init__(self, repo: TransactionRepository) -> None:
        self._repo = repo

    def execute(self, scope: MerchantScope, transaction_id: str) -> Transaction:
        tx = self._repo.get(scope, transaction_id)
        if tx is None:  # also when it belongs to another merchant: never reveal existence
            raise NotFound(f"Transaction {transaction_id} not found")
        return tx
