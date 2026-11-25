from datetime import date
from decimal import Decimal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.container import get_run_growth_simulation, get_scope, get_today
from app.contexts.simulation.application.run_simulation import RunGrowthSimulation
from app.contexts.simulation.domain.growth import Assumptions
from app.shared.api.schemas import MoneyOut, PeriodOut, period_from_query
from app.shared.domain.merchant_scope import MerchantScope

router = APIRouter(prefix="/simulations", tags=["simulation"])


class SimulationIn(BaseModel):
    baseline_from: date | None = None
    baseline_to: date | None = None
    volume_growth: float = Field(default=0.15, ge=-1, le=10)
    acceptance_change: float = Field(default=0.0, ge=-1, le=1)  # absolute points
    ticket_change: float = Field(default=0.0, gt=-1, le=10)  # relative


class BaselineOut(BaseModel):
    period: PeriodOut
    total_count: int
    accepted_count: int
    acceptance_share: float  # accepted / all initiated: makes count x share x ticket reconcile
    average_ticket: MoneyOut
    gross_collection: MoneyOut


class AssumptionsOut(BaseModel):
    volume_growth: float
    acceptance_change: float
    ticket_change: float


class ProjectionOut(BaseModel):
    projected_count: int
    projected_accepted_count: float
    projected_acceptance_share: float
    projected_average_ticket: MoneyOut
    projected_collection: MoneyOut
    delta_collection: MoneyOut
    delta_pct: float | None


class SimulationOut(BaseModel):
    baseline: BaselineOut
    assumptions: AssumptionsOut
    projection: ProjectionOut
    monthly_goal: MoneyOut | None
    goal_gap: MoneyOut | None  # projection - goal; positive means the goal is covered


@router.post("/growth", response_model=SimulationOut)
def growth(
    body: SimulationIn,
    scope: MerchantScope = Depends(get_scope),
    today: date = Depends(get_today),
    uc: RunGrowthSimulation = Depends(get_run_growth_simulation),
) -> SimulationOut:
    assumptions = Assumptions(
        volume_growth=Decimal(str(body.volume_growth)),
        acceptance_change=Decimal(str(body.acceptance_change)),
        ticket_change=Decimal(str(body.ticket_change)),
    )
    r = uc.execute(scope, period_from_query(body.baseline_from, body.baseline_to, today), assumptions)
    k, p = r.baseline_kpis, r.projection
    return SimulationOut(
        baseline=BaselineOut(
            period=PeriodOut.of(r.baseline_period),
            total_count=k.total_count,
            accepted_count=k.accepted_count,
            acceptance_share=float(r.baseline.acceptance_share),
            average_ticket=MoneyOut.of(r.baseline.average_ticket),
            gross_collection=MoneyOut.of(k.gross_collected),
        ),
        assumptions=AssumptionsOut(
            volume_growth=float(r.assumptions.volume_growth),
            acceptance_change=float(r.assumptions.acceptance_change),
            ticket_change=float(r.assumptions.ticket_change),
        ),
        projection=ProjectionOut(
            projected_count=p.projected_count,
            projected_accepted_count=float(p.projected_accepted_count),
            projected_acceptance_share=float(p.projected_acceptance_share),
            projected_average_ticket=MoneyOut.of(p.projected_average_ticket),
            projected_collection=MoneyOut.of(p.projected_collection),
            delta_collection=MoneyOut.of(p.delta_collection),
            delta_pct=float(p.delta_pct) if p.delta_pct is not None else None,
        ),
        monthly_goal=MoneyOut.of(r.monthly_goal) if r.monthly_goal else None,
        goal_gap=MoneyOut.of(r.goal_gap) if r.goal_gap is not None else None,
    )
