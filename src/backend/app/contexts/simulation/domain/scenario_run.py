"""Audit trail of a what-if run: the inputs the merchant chose and the projection shown."""

from dataclasses import dataclass

from app.contexts.simulation.domain.growth import Assumptions, Projection
from app.shared.domain.date_range import DateRange


@dataclass(frozen=True, slots=True)
class ScenarioRun:
    merchant_id: str
    created_by: int
    baseline_period: DateRange
    assumptions: Assumptions
    projection: Projection
