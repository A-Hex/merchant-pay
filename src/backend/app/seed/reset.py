"""Reset the demo database to a known state.  Usage:  python -m app.seed.reset

1. wipe all rows   2. synthetic demo merchants + users   3. challenge workbook if present
"""

import sys
from pathlib import Path

from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.config import get_settings
from app.container import _session_factory, get_password_hasher, get_today
from app.contexts.alerts.application.evaluate_alerts import EvaluateAlerts
from app.contexts.alerts.infrastructure.sql_alert_repository import SqlAlertRepository
from app.contexts.identity.infrastructure.sql_repositories import SqlMerchantRepository
from app.contexts.ledger.application.import_transactions import ImportTransactions
from app.contexts.ledger.infrastructure.file_sources import read_any
from app.contexts.ledger.infrastructure.sql_transaction_repository import (
    SqlMerchantRegistry,
    SqlTransactionRepository,
)
from app.db.base import Base
from app.seed.accounts import ensure_merchant, ensure_user
from app.seed.synthetic_demo import DEMO_MERCHANTS, generate_rows
from app.shared.domain.enums import DataOrigin
from app.shared.domain.merchant_scope import MerchantScope

DEMO_PASSWORD = "demo1234"  # synthetic demo accounts only


def _importer(s: Session) -> ImportTransactions:
    return ImportTransactions(SqlTransactionRepository(s), SqlMerchantRegistry(s))


def wipe(s: Session) -> None:
    for table in reversed(Base.metadata.sorted_tables):
        s.execute(delete(table))


def seed_synthetic(s: Session) -> None:
    hasher = get_password_hasher()
    for i, m in enumerate(DEMO_MERCHANTS, start=1):
        ensure_merchant(s, m.merchant_id, m.display_name, m.category, m.monthly_goal_centimes)
        report = _importer(s).execute(generate_rows(m), source_name=f"synthetic:{m.merchant_id}",
                                      data_origin=DataOrigin.SYNTHETIC_DEMO)
        if not report.ok:
            raise SystemExit(f"Synthetic import failed: {report.errors[:5]}")
        email = "demo@ceo-pay.test" if i == 1 else f"demo{i}@ceo-pay.test"
        ensure_user(s, hasher, email, DEMO_PASSWORD, m.merchant_id)
        print(f"  {m.merchant_id}: {report.imported_rows} synthetic rows -> {email}")


def seed_workbook(s: Session, source_dir: Path) -> None:
    files = sorted([*source_dir.glob("*.xlsx"), *source_dir.glob("*.csv")])
    if not files:
        print(f"  no workbook in {source_dir} (skipped)")
        return
    for path in files:
        report = _importer(s).execute(read_any(path), source_name=path.name,
                                      data_origin=DataOrigin.CHALLENGE_SOURCE)
        if not report.ok:
            print(f"  {path.name}: REJECTED, {len(report.errors)} errors")
            for e in report.errors[:20]:
                print(f"    row {e.row_number} [{e.field}] {e.message}")
            continue
        print(f"  {path.name}: {report.imported_rows} rows (batch {report.batch_id})")
    # map a demo owner to the first workbook merchant
    from app.db.models import MerchantRow
    first = s.query(MerchantRow).filter(~MerchantRow.merchant_id.like("M-DEMO-%")) \
        .order_by(MerchantRow.merchant_id).first()
    if first:
        ensure_user(s, get_password_hasher(), "owner@ceo-pay.test", DEMO_PASSWORD,
                    first.merchant_id)
        print(f"  owner@ceo-pay.test -> {first.merchant_id}")


def seed_alerts(s: Session) -> None:
    """Evaluate the alert rules for the demo merchants so the jury sees alerts after `make seed`."""
    today = get_today(get_settings())
    evaluator = EvaluateAlerts(SqlTransactionRepository(s), SqlAlertRepository(s),
                               SqlMerchantRepository(s))
    for m in DEMO_MERCHANTS:
        # system scope: seeding is not a merchant request, it is the fixture builder
        scope = MerchantScope(user_id=0, merchant_id=m.merchant_id, role="owner")
        result = evaluator.execute(scope, today)
        print(f"  {m.merchant_id}: {len(result.created)} alert(s) on {today}")


def main() -> None:
    source_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else get_settings().data_dir / "source"
    with _session_factory()() as s, s.begin():
        print("Wiping data...")
        wipe(s)
        print("Seeding synthetic demo merchants...")
        seed_synthetic(s)
        print("Importing challenge workbook...")
        seed_workbook(s, source_dir)
        print("Evaluating alerts...")
        seed_alerts(s)
    print(f"Done. Demo password for all accounts: {DEMO_PASSWORD}")


if __name__ == "__main__":
    main()
