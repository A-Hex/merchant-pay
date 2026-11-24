# CEO-Pay

You are the principal engineer, ML architect, cybersecurity engineer, fintech domain expert, product designer, and QA lead for Merchant Pay.

Repository:
https://github.com/A-Hex/merchant-pay

Transform the existing repository into a complete, production-quality merchant financial intelligence platform. Continue from the current codebase. Do not rebuild from scratch, discard existing work, reset branches, or replace working modules with generic templates.

Work autonomously until the product is complete, tested, secure, polished, and demonstrable. Do not stop at planning, scaffolding, mock screens, placeholder components, or a written explanation.

## Operating principles

- Inspect the repository before changing anything.
- Read README.md, docs/TEAM_PLAN.md, docs/architecture.md, docs/metric_definitions.md, docs/demo_runbook.md, and docs/blueprint.pdf.
- Inspect git status, existing tests, migrations, API contracts, and uncommitted work.
- Preserve valuable existing implementation.
- Make small, coherent changes and test every meaningful change.
- Fix failures before continuing to the next incomplete area.
- Make reasonable engineering decisions without repeatedly asking for approval.
- Never claim completion while functionality is incomplete.
- Never create fake data, fake metrics, fake testimonials, fake compliance certifications, or unsupported security claims.

## Architecture

Respect the existing modular monolith:

- Backend: Python 3.12, FastAPI, SQLAlchemy, Alembic, PostgreSQL, Pydantic
- Frontend: React, TypeScript, Vite, TanStack Query, Recharts
- Localization: French and Arabic, including correct Arabic RTL behavior
- Bounded contexts: identity, ledger, analytics, alerts, simulation
- Dependency direction: api -> application -> domain
- Infrastructure implements application ports

Keep the domain independent from FastAPI, SQLAlchemy, HTTP, and infrastructure details.

## Product capabilities

Complete these end-to-end:

1. Secure authentication and logout
2. Merchant profile viewing and editing
3. Strict merchant tenant isolation
4. Transaction ledger with filtering, pagination, and detail view
5. Collection summaries with accepted, declined, cancelled, and refunded amounts separated
6. Dashboard KPIs, trends, channel analysis, and period comparison
7. Explainable alerts with evidence, thresholds, baselines, and denominators
8. Alert acknowledgement and resolution
9. Growth simulation with transparent assumptions
10. Decline-rate intelligence with uncertainty and insufficient-data handling
11. Audit logging and security observability
12. French and Arabic localization with RTL support
13. Responsive mobile and desktop layouts
14. Loading, empty, error, success, and retry states
15. Reproducible seed data and complete demo runbook

Every user-facing flow must use the real backend. Do not hide missing functionality behind static mock data.

## Fintech correctness

- Use the existing Money value object or integer centimes.
- Never use floating point for money.
- Keep currency explicit, especially DZD.
- Never silently mix currencies.
- Preserve transaction status distinctions and avoid double counting.
- Use explicit date ranges and timezone behavior.
- Handle zero denominators and empty periods safely.
- Make simulator results deterministic and reproducible.
- Show assumptions beside projections.
- Add tests for every financial formula.
- ML outputs are advisory and must never overwrite ledger truth.

## ML and deep-learning engine

Build an extensible, responsible intelligence layer. Do not add deep learning only for appearance. If the available data is insufficient, use interpretable statistics and document why.

The engine must support:

- Feature extraction and validation
- Feature and method versioning
- Reproducible inference
- Confidence or uncertainty values
- Explanation objects
- Data sufficiency checks
- Safe fallbacks
- Audit records for generated insights

Implement, where justified by available data:

- Rolling decline-rate analysis
- Baseline comparisons
- Beta-Binomial posterior or another justified statistical method
- Posterior mean and credible interval
- Sample size and insufficient-data checks
- Robust anomaly detection such as median absolute deviation or EWMA
- Forecasting only with adequate history, backtesting, and prediction intervals
- Evidence-based merchant recommendations

Every intelligence result must include the signal, value, baseline, sample size, uncertainty, explanation, limitation, recommended action, source period, and method version.

Never present a weak signal as certainty. Never expose hidden chain-of-thought. Return concise, auditable explanations only.

## Cybersecurity requirements

- Use secure password hashing and secure cookie or token handling.
- Enforce authentication and token expiration.
- Never store secrets in source code or logs.
- Enforce MerchantScope server-side on every merchant endpoint.
- Never trust merchant IDs from the client.
- Enforce tenant scope in every repository query and write.
- Test cross-tenant reads and writes.
- Use safe errors that do not reveal another tenant's data.
- Validate all input and prevent injection, IDOR, mass assignment, and unsafe file-import issues.
- Add login throttling and sensible request limits.
- Add request IDs and security-relevant audit events.
- Never log passwords, tokens, cookies, credentials, or unnecessary payment data.
- Do not claim PCI DSS, SOC 2, ISO 27001, or regulatory compliance without verified evidence.
- Add regression tests for authentication, authorization, tenant isolation, throttling, malformed input, imports, errors, and audit logging.

## UI and UX quality

Create a distinct Merchant Pay identity. The interface must be clear, trustworthy, responsive, accessible, and useful in real merchant workflows.

- Establish a coherent visual system before adding pages.
- Use color for financial meaning and risk, not decoration.
- Make numbers easy to scan and trace to their source period.
- Provide useful empty and error states.
- Keep layout stable during loading.
- Make every button and link functional.
- Provide form validation and recovery actions.
- Make charts readable without relying on color alone.
- Support keyboard navigation, screen readers, and visible focus states.
- Test at 375px, tablet, and desktop widths.
- Ensure Arabic RTL works across navigation, tables, charts, forms, and drawers.

Avoid generic AI-generated UI patterns: blue-purple gradients, neon decoration, excessive glassmorphism, glowing cards, pill-shaped everything, generic bento grids, fake terminal windows, repetitive feature cards, fake trust logos, fake statistics, generic AI labels, fabricated testimonials, excessive animation, and copied Stripe, Linear, Vercel, or Notion styling.

Do not use the em dash character in user-facing copy.

## Completion workflow

Repeat this loop until complete:

1. Read the relevant code.
2. Identify one concrete missing or defective behavior.
3. Implement it.
4. Add or update tests.
5. Run targeted tests.
6. Run the complete relevant test suite.
7. Fix every failure.
8. Update documentation.
9. Continue.

Verify at minimum:

- make install
- make up
- make seed
- make test
- make lint
- frontend typecheck
- frontend production build
- API type generation
- clean database initialization
- complete demo runbook

## Final delivery gate

Do not declare completion until:

- The application starts from a clean setup.
- Demo users can log in.
- Tenant isolation is verified.
- Financial totals reconcile with ledger records.
- Alerts have evidence and explanations.
- Simulator results are reproducible.
- Intelligence features show uncertainty and limitations.
- No user-facing placeholder, dead button, or broken route remains.
- No merchant endpoint bypasses scope.
- No monetary calculation uses floating point.
- No sensitive information is logged.
- No fake business claim exists.
- French, Arabic, RTL, mobile, keyboard navigation, and error recovery work.
- Backend tests pass.
- Frontend typecheck and production build pass.
- Lint passes or every remaining warning is justified.
- Documentation matches the implementation.

Finish with a concise report containing completed features, ML methods, security controls, important files, tests executed, known limitations, and exact setup and demo commands.

Continue working until the delivery gate passes. Do not stop after producing a plan.
