# CEO-Pay: critical review (Stage A) and delivery plan (Stage B)

*CEO-Pay — Merchant Pay solution by UMCBOT for FINOVIA × ENSM × SATIM.*
Review date 2026-11-25, branch `ceo-pay` (= team PR stack #4–#8 + CEO-Pay branding).
Labels: **[F]** verified fact (command/test/file cited) · **[A]** assumption · **[P]** proposal.

## 1. Executive verdict

- **What it is today [F].** A working merchant collection-analytics product: all six mandatory flows run
  end to end on a deterministic seed. The backend is a clean modular monolith (124 backend tests pass).
  The FR/AR UI follows the shadcn-fintech design system.
- **Strongest advantage [F].** Figures you can verify. The dashboard, collections and raw ledger agree
  to the centime for all four statuses on the demo period (probe below). Every alert, insight and
  scenario shows its denominator, baseline and assumptions.
- **Largest weakness [F].** No report or export path. A merchant can't take numbers out of the app (no
  CSV/PDF, no sharing), and the brief's Reports & Sharing job is missing. Also, one displayed simulator
  indicator is wrong (FIN-001).
- **Single most valuable next move [P].** Fix FIN-001, then add a server-generated, merchant-scoped,
  aggregated *Collections Summary* report (PDF + safe CSV) with an honest "Share via WhatsApp" handoff.
  This closes the take-the-numbers-to-my-accountant job without adding any new financial maths.

## 2. Repository reality report

| Area | State | Evidence |
|---|---|---|
| Auth, profile, tenant scope | verified working | `tests/integration/test_api.py`, `test_profile_api.py`, cross-tenant 404 tests |
| Ledger search/filter/detail + provenance | verified working | `test_api.py::test_ledger_is_scoped_and_filters_combine` |
| Collections A vs B, status-separated | verified working | `test_collections_api.py`; live probe §4 |
| Dashboard KPIs, trend, channels, activity periods | verified working | `test_insights_api.py`, live probe |
| Alerts (drop, decline spike, inactivity, goal) | verified working | `test_alerts_api.py`; 2 alerts after `make seed` |
| Growth simulator +15 % | **partially correct** | projection is exact, but `goal_gap` is wrong (FIN-001) |
| Scenario Lab, Pulse, Radar, Customers, Loyalty | verified working | 19 + 12 + 8 dedicated tests |
| Official workbook import | **untested here** | workbook not in repo (git-ignored, correctly). The header mapping is only tested on fixture rows |
| Reports / exports / sharing | not implemented | no export endpoint in `app/contexts/*` |
| `PlaceholderPage.tsx` | dead file | no imports (`grep`) |
| `docs/TEAM_PLAN.md` | **drifted** | 18 unchecked items, most already delivered |

## 3. Official challenge traceability

| # | Requirement | Backend | Frontend | Tests | Demo step |
|---|---|---|---|---|---|
| 1 | Account, profile, workspace | `identity/*`, `PATCH /merchant/me` | `LoginPage`, `ProfilePage`, `Layout` | `test_api`, `test_profile_api`, `test_auth_security` | 1 |
| 2 | Transactions: list, search, period/status filter, detail | `ledger/*`, `/transactions` | `TransactionsPage`, `TransactionDrawer` | `test_api` | 2 |
| 3 | Collections, status-separated | `analytics/get_collections.py` | `CollectionsPage` | `test_collections_api` | 3 |
| 4 | Count, total, average, evolution, channels, strong/weak periods | `kpis.py`, `activity.py` | `DashboardPage`, `ActivityCard` | `test_kpis`, `test_insights` | 1, 4a |
| 5 | Alerts: drop, inactivity, decline increase, goal reached | `alerts/domain/rules.py` | `AlertsPage`, dashboard panel | `test_alerts_*` | 5 |
| 6 | Growth simulator (+15 %) vs current | `simulation/growth.py`, `scenario_lab.py` | `SimulatorPage`, `ScenarioLab` | `test_alerts_and_simulation`, `test_scenario_lab*` | 6 |

## 4. Financial correctness audit

**Reconciliation probe [F]** (live API, demo merchant, 7–20 Nov). Values in centimes:

| Status | Dashboard | Collections | Ledger rows (sum) |
|---|---|---|---|
| accepted | 25 135 650 | 25 135 650 | 25 135 650 (64 rows) |
| declined | 5 490 510 | — | 5 490 510 (10 rows) |
| cancelled | 564 159 | — | 564 159 (2) |
| refunded | 227 759 | — | 227 759 (1) |

Formula register: `docs/metric_definitions.md` (status treatment, denominators, zero-baseline states,
count vs amount share, Money in centimes with ROUND_HALF_UP). It matches the implementation:
`kpis.py`, `period_comparison.py`, `growth.py`, `pulse.py`, `scenario_lab.py`, each with tests.

**Findings**

| ID | Sev | Evidence | Problem → root cause | Fix [P] | Acceptance test | Effort |
|---|---|---|---|---|---|---|
| FIN-001 | **P0** | `run_simulation.py::SimulationResult.goal_gap`; probe: 14-day +15 % projection 289 059,98 vs **monthly** goal 1 500 000 → gap −1 210 940,02 | Compares amounts over different time spans; the goal is never pro-rated | Pro-rate the goal to the baseline length (goal × days / 30, the Lab's rule) and expose `goal_for_period` | 14-day baseline: gap = projection − goal × 14/30 | S |
| FIN-002 | P1 | `pulse.py::_goal_item` uses calendar days | "Needed per day" ignores the merchant's operating days (`merchants.operating_days`) | Count remaining **operating** days; fall back to calendar days when none are configured | Closed Fridays: needed/day = remaining ÷ open days left | S |
| FIN-003 | P2 | no fee data in the 7 fields | Net proceeds can't be computed honestly | Optional merchant-entered fee schedule (deferred); UI already says "gross" | — | M |
| FIN-004 | P2 | refunds not linked to the original sale | Refund-adjusted collections are impossible | Keep the separate display (already done); needs `original_transaction_id` | — | — |

Category-error check [F]: no screen calls collections "profit". Declined value is labelled "valeur
refusée / opportunité", the simulator and Lab say "pas une prévision", and loyalty points are a cost
and liability (Rewards Studio).

## 5. Security review

Threat model (multi-tenant analytics, synthetic data, no payment execution, no card data):

| Threat | Control today [F] | Gap / remediation |
|---|---|---|
| Cross-merchant access (IDOR) | `get_scope` on every merchant route; repository reads take `scope`; 404 on foreign IDs/tokens | — (tests cover ledger, customers, loyalty, profile, simulations) |
| Brute force, enumeration | Throttle 5/acct+IP, 20/IP per 15 min; generic 401 | in-memory only (documented) |
| Session theft / CSRF | JWT in httpOnly SameSite=Lax cookie; no state-changing GET | **SEC-001 P1:** add an Origin check on unsafe methods (defence in depth); `cookie_secure` defaults to `false` (documented as dev-only) |
| XSS / clickjacking | React escaping, no `dangerouslySetInnerHTML` | **SEC-002 P1:** no security headers (`main.py` only adds CORS). Add nosniff, frame-ancestors/X-Frame-Options, Referrer-Policy, Permissions-Policy |
| SQL injection | SQLAlchemy parameters; `ilike` input bound | — |
| Malicious imports | All-or-nothing, row validation; import is CLI/seed only (no upload endpoint) | an upload endpoint would need size/type/row limits (none exist today) |
| CSV formula injection | no export yet | must be neutralised in the new export (REP-001) |
| Data leakage in logs | Throttle logs IP only; audit entries mask customer tokens | — |
| Reward abuse | DB-unique idempotency key; negative balance raises | — |

PCI DSS: **not claimed.** CEO-Pay stores no card data and executes no payments.

## 6. UX review (screen by screen)

| Screen | Strength [F] | Fix [P] | Sev |
|---|---|---|---|
| Login | Split brand panel, staggered form, password toggle | Add positioning line + UMCBOT/challenge credit | P1 (BR-001) |
| Dashboard | Answers what / vs-before / what changed / which channel / next step (KPIs → Pulse → trend → activity → channel/status → alerts) | — | — |
| Transactions / drawer | Filters in URL, provenance in the sliding sheet | — | — |
| Insights (Radar) | Intervals, gates, method card | prior-sensitivity note (ML-001) | P2 |
| Customers → Win-back | Evidence per customer | 48 entries in one list → paginate (UX-001) | P2 |
| Simulator | Exact +15 %, Lab bridge | Goal gap label after the FIN-001 fix | P0 |
| Profile/Settings | Validated owner-only edit | **No Reports & Sharing** (REP-001) | P1 |
| Global | Theme, ⌘K, RTL sidebar, reduced motion | Arabic chart axes now widened | — |

## 7. AI/ML review

- **Beta-Binomial decline signal [F].** Prior Beta(1,19), decision counts only, 90 % *credible*
  interval, n ≥ 20 gate, exact P(higher). Deterministic: closed-form maths with no sampling. ML-001 [P]:
  disclose prior sensitivity. Computed [F] for the demo period: overall P(higher) = 0.9882 with Beta(1,19),
  0.9937 with Beta(1,1) and 0.9818 with Beta(2,38). The overall verdict "elevated" is unchanged; e-commerce
  P = 0.99–1.00 under all three, but it stays "insufficient data" because of the n ≥ 20 gate, not the prior.
- **Win-back radar.** A heuristic band (median/MAD), explicitly not a probability. 14/14 planted
  drifters recovered without labels (`test_customer_fixture`).
- **Do not use ML here [F].** Forecasting (the synthetic history has no seasonality; official workbook
  has 150 rows, 1–9 per merchant), churn classifiers (no labels), Isolation Forest, deep learning. The
  roadmap needs ≥ 6 months of daily data and a naive-baseline backtest (MAE/WAPE) before any forecast.

## 8. Customer loyalty feasibility

Implemented on an optional merchant-scoped `customer_token` (synthetic fixture only; the importer
refuses card-like values). Without tokens the pages say "unavailable" (`demo2`). Real use needs
consented, pseudonymous tokens from the acceptance side, and refund linkage before points can be reversed.

## 9. Business model (hypotheses, not validated)

| Tier | Contents | Test with pilots |
|---|---|---|
| Starter | ledger, collections, dashboard, standard alerts | activation, weekly use |
| Growth | Pulse, Radar, Scenario Lab, reports & sharing | report-share frequency, willingness to pay (WTP) interviews |
| Pro | customers, loyalty economics, multi-store | retention of tokenised merchants |
| Partner | aggregated portfolios for an authorised acquirer | requires a separate access model |

No transaction fee (CEO-Pay doesn't move money). Unit economics inputs (all *assumed* until a pilot):
price per tier, hosting and support cost per merchant, CAC, monthly churn → MRR, gross margin, break-even
merchant count. Validation: 10–15 merchant interviews, a 6-week pilot with usage telemetry, and
Van Westendorp pricing tests.

## 10. Prioritised backlog (Stage B order)

| ID | Pri | Item | Acceptance | Effort | Status |
|---|---|---|---|---|---|
| FIN-001 | P0 | Pro-rate the goal in `/simulations/growth` | unit + API test | S | → Stage B |
| DOC-001 | P0 | TEAM_PLAN/README drift; delete `PlaceholderPage.tsx` | docs match tests | S | → Stage B |
| BR-001 | P1 | Positioning line, tagline, UMCBOT/challenge credit | login, README | S | → Stage B |
| SEC-001/002 | P1 | Origin check on unsafe methods + security headers | integration tests | S | → Stage B |
| FIN-002 | P1 | Goal pace on operating days | unit test | S | → Stage B |
| REP-001 | P1 | Reports & Sharing: scoped aggregated PDF/CSV, preview, WhatsApp handoff | reconciliation, isolation, formula-injection, share-state tests | M | → Stage B |
| UX-001 | P2 | Paginate the win-back list | — | S | deferred |
| ML-001 | P2 | Prior-sensitivity disclosure | — | S | deferred |
| FIN-003 | P2 | Fee schedule (merchant-entered) | — | M | deferred |
| — | P3 | Multi-store, settlement, billing | — | L | future |

## 11. Architecture change list (Stage B)

- `simulation/application/run_simulation.py`, `simulation/api/router.py`: `goal_for_period`, pro-rated `goal_gap`.
- `analytics/domain/pulse.py` (+ `get_insights.py`): operating-day pace.
- `app/shared/api/security.py` (new) + `main.py`: headers and Origin guard.
- `app/contexts/reports/` (new bounded context): `domain/summary.py` (reuses `compute_kpis`, `channel_mix`),
  `domain/csv_safe.py`, `infrastructure/pdf.py` (reportlab), `api/router.py` (`/reports/collections-summary`).
- Frontend: `features/merchant/ReportsCard.tsx` (Settings → Reports & Sharing), i18n FR/AR.

## 12. Test plan

Unit: goal pro-rating, operating-day pace, summary aggregation, CSV neutralisation, safe filenames.
Integration: report reconciles with `/collections/summary`; another merchant gets their own report and never
this one's; anonymous → 401; malformed period → 422; Origin guard (foreign Origin → 403, same origin and
no Origin → allowed); headers present. Browser: preview, download, share-capability detection,
cancelled share, FR/AR, 390 px. Regression: full backend suite + `tsc` + build.

## 13. Jury narrative

*Épicerie Démo Boumerdès* collected **251 356,50 DA** from 7 to 20 Nov, **−50.9 %** like-for-like. The
Pulse splits the drop exactly: fewer transactions (−281 006,14) partly offset by a bigger basket
(+20 787,36). Declines rose to 13.5 % (P = 98.8 %), with 78.8 % of the declined value on e-commerce, which
is still "insufficient data" at channel level (17 attempts). Win-back shows 22 regulars drifting from
their own rhythm. The Scenario Lab shows what +15 % volume is worth, and what moving e-commerce volume to
POS adds. The merchant then shares an accurate aggregated summary with their accountant via WhatsApp,
staying in control of the recipient and the final send.
