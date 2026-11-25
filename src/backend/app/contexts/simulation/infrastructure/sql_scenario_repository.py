"""SQLAlchemy adapter persisting scenario runs (audit of what the merchant was shown)."""

from sqlalchemy.orm import Session

from app.contexts.simulation.domain.scenario_run import ScenarioRun
from app.db.models import ScenarioRunRow


class SqlScenarioRunRepository:
    def __init__(self, session: Session) -> None:
        self._s = session

    def save(self, run: ScenarioRun) -> None:
        a = run.assumptions
        self._s.add(ScenarioRunRow(
            merchant_id=run.merchant_id,
            created_by=run.created_by,
            baseline_start=run.baseline_period.start,
            baseline_end=run.baseline_period.end,
            # Decimals stored as strings so the assumptions JSON round-trips exactly.
            assumptions={
                "volume_growth": str(a.volume_growth),
                "acceptance_change": str(a.acceptance_change),
                "ticket_change": str(a.ticket_change),
            },
            projected_count=run.projection.projected_count,
            projected_collection_centimes=run.projection.projected_collection.centimes,
        ))
        self._s.flush()
