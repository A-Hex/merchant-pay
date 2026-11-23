from app.contexts.ledger.application.import_transactions import ImportTransactions
from app.shared.domain.enums import DataOrigin


class FakeWriter:
    def __init__(self, existing=()):
        self.existing, self.saved = set(existing), []

    def existing_ids(self, ids):
        return self.existing & set(ids)

    def save_batch(self, batch, txs):
        self.saved.append((batch, txs))


class FakeMerchants:
    def ensure_exists(self, categories):
        self.seen = categories


def _row(tid="T1", **over):
    base = {"transaction_id": tid, "merchant_id": "M1", "occurred_at": "2026-11-01 10:00:00",
            "amount": "1200.50", "channel": "E-commerce", "status": "Accepted", "category": "Retail"}
    return {**base, **over}


def _run(rows, writer=None):
    writer = writer or FakeWriter()
    uc = ImportTransactions(writer, FakeMerchants(), id_factory=lambda: "batch-1")
    return uc.execute(enumerate(rows, start=2), source_name="t.xlsx",
                      data_origin=DataOrigin.CHALLENGE_SOURCE), writer


def test_valid_rows_are_saved_with_provenance():
    report, writer = _run([_row("T1"), _row("T2")])
    assert report.ok and report.imported_rows == 2
    batch, txs = writer.saved[0]
    assert batch.batch_id == "batch-1" and all(t.source_batch_id == "batch-1" for t in txs)


def test_any_error_rejects_whole_batch_with_row_report():
    report, writer = _run([_row("T1"), _row("T1"), _row("T3", amount="abc"),
                           _row("T4", status="Pending"), _row("T5", occurred_at="")])
    assert not report.ok and writer.saved == []
    assert [(e.row_number, e.field) for e in report.errors] == [
        (3, "transaction_id"), (4, "amount"), (5, "status"), (6, "occurred_at")]


def test_already_imported_ids_are_rejected():
    report, _ = _run([_row("T1")], FakeWriter(existing={"T1"}))
    assert not report.ok and "already imported" in report.errors[0].message
