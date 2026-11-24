"""Append-only audit trail.

Audit rows are written inside the request's unit of work: if the business action rolls
back, so does its audit entry (no phantom records). Failed logins are deliberately not
stored here because their transaction is rolled back; they go to the structured security
log instead (see ``app/shared/api/middleware.py``).
"""

from sqlalchemy.orm import Session

from app.db.models import AuditEventRow


class SqlAuditRepository:
    def __init__(self, session: Session) -> None:
        self._s = session

    def record(self, actor_id: int | None, action: str, entity_ref: str) -> None:
        self._s.add(AuditEventRow(actor_id=actor_id, action=action[:64], entity_ref=entity_ref[:255]))
