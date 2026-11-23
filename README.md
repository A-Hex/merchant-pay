# Merchant Pay — Intelligent Merchant Financial Management

> FINOVIA × ENSM × SATIM challenge. A merchant-facing web app that turns electronic payment
> records into reliable collection visibility, explainable alerts and transparent growth scenarios.

**Design thesis:** make the financial core *boringly correct* and the intelligence *unusually
honest*. Every KPI reconciles with the ledger, every alert shows its evidence, every scenario
shows its assumptions. See [`docs/blueprint.pdf`](docs/blueprint.pdf).

## Quickstart

Prerequisites: Docker, [uv](https://docs.astral.sh/uv/), Node 20+.

```bash
make install        # backend (uv) + frontend (npm) dependencies
make up seed        # Postgres + API on :8000, then load the deterministic demo data
cp src/frontend/.env.example src/frontend/.env.local
make dev-front      # web app on http://localhost:5173
```

API docs: http://localhost:8000/api/docs. To include the challenge workbook, drop
`Inventory_Report_Template.xlsx` into `data/source/` and run `make seed` again.

### Demo accounts (synthetic data only)

| Email | Password | Merchant |
|---|---|---|
| `demo@merchantpay.test` | `demo1234` | `M-DEMO-01`, hero merchant with a planted decline spike and collection drop |
| `demo2@merchantpay.test` | `demo1234` | `M-DEMO-02`, used to show tenant isolation |
| `owner@merchantpay.test` | `demo1234` | first merchant of the challenge workbook (only if it was imported) |

## Architecture

A **modular monolith** with **Clean Architecture inside each bounded context** and DDD value objects.

```
React + TS (Vite) ── typed client generated from OpenAPI
        │ /api/v1 (httpOnly session cookie)
FastAPI ── container.py (composition root, dependency injection via Depends)
   ├── identity    auth, merchant access, MerchantScope
   ├── ledger      transactions, import + provenance
   ├── analytics   KPIs, period comparison (pure domain functions)
   ├── alerts      Alert aggregate (state machine) + rules (Strategy)
   └── simulation  growth what-if (pure domain function)
        each context: api → application → domain ← infrastructure
PostgreSQL (SQLAlchemy 2 + Alembic)
```

Details, rules and recipes: [`docs/architecture.md`](docs/architecture.md).
Metric formulas: [`docs/metric_definitions.md`](docs/metric_definitions.md).

## Project structure

```
src/backend/    FastAPI app (app/), tests (tests/), Alembic migrations
src/frontend/   React app (src/features/* per module)
data/source/    challenge workbook (not committed)
docs/           architecture, metrics, team plan, demo runbook, blueprint
```

## Commands

| Command | What it does |
|---|---|
| `make test` | backend unit + integration tests, frontend type-check |
| `make lint` | ruff + tsc |
| `make gen-api` | regenerate `src/frontend/src/api/schema.d.ts` from the FastAPI schema |
| `make seed` | wipe and reseed demo data (deterministic) |
| `make dev-back` | run the API locally with reload (needs `docker compose up -d db`) |

## Tech stack

FastAPI · SQLAlchemy 2 · Alembic · PostgreSQL 16 · Pydantic v2 · PyJWT · Argon2 · pytest ·
React 19 · TypeScript · Vite · Tailwind CSS 4 · TanStack Query · React Router · react-i18next (FR / AR, RTL) · Recharts.

## Data and security policy

- Synthetic data only. There is no live payment processing and no SATIM or bank connectivity.
- No card PAN, CVV, PIN or OTP is ever stored.
- Synthetic rows are tagged `data_origin=synthetic_demo`, and every row keeps its `source_batch_id`.
- Tenant isolation is enforced server-side: merchant scope comes from the user's access mapping,
  never from a client-supplied ID.
- Money is stored and computed as integer centimes (DZD), never as floats.

## License

[MIT](LICENSE)
