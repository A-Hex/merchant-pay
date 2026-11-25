# CEO-Pay: authentication and authorisation specification

Status: **implemented and tested** unless marked *(gap)*. Code: `app/contexts/identity/**`,
`app/container.py`, `app/shared/api/security.py`. Tests: `tests/integration/test_api.py`,
`test_auth_security.py`, `test_login_history_api.py`, `test_profile_api.py`, `tests/unit/test_login_throttle.py`,
`test_login_history.py`.

## 1. Scope and threat model

CEO-Pay is a multi-tenant analytics prototype on synthetic payment data. It stores no card data and
executes no payments, and it does **not** claim PCI DSS. Assets to protect: a merchant's collection
figures, reports, customer pseudonyms and loyalty data. Main threats: cross-merchant access (IDOR),
credential guessing, session theft, cross-site request forgery, and leakage through logs or exports.

## 2. Identities

| Object | Meaning |
|---|---|
| `User` | a person who signs in (`users`: e-mail, Argon2 hash, status `active` / `disabled`) |
| `Merchant` | a shop (`merchants`) |
| `MerchantAccess` | grant of a user to a merchant with a role: `owner` or `staff` (`user_merchant_access`) |
| `MerchantScope` | server-built context `(user_id, merchant_id, role)` passed to every merchant query |

**Account creation.** Accounts are provisioned by the seed (`app/seed/reset.py`). There is no
self-registration: the challenge allows a simulated sign-up, and self-service sign-up would need
e-mail verification and merchant onboarding *(gap, out of prototype scope)*.

## 3. Sign-in: `POST /api/v1/auth/login`

Body `{email, password}` (validated: e-mail 3–254 chars, password 1–128). Flow:

1. **Cross-site guard.** A request carrying an `Origin` that is neither this host (`Host` or the dev proxy's
   `X-Forwarded-Host`) nor in `CORS_ORIGINS` gets **403** `OriginRefused` (§7).
2. **Throttle.** More than 5 failures per (e-mail, IP) or 20 per IP in a 15-minute sliding window gives
   **429** with `Retry-After`. The throttle is in memory and per process *(gap: a shared store for several replicas)*.
3. **Verify.** E-mail is lower-cased; the user must exist, be `active`, and the Argon2 hash must match.
   Any failure gives the same **401** "Invalid email or password", so accounts can't be enumerated.
4. **Session.** A JWT (HS256, `sub` = user id, `exp` = `JWT_TTL_MINUTES`, default 480) is set as
   cookie `mp_session` with `HttpOnly`, `SameSite=Lax`, `Secure` when `COOKIE_SECURE=true`, and `Max-Age` = TTL.
   The token is never readable by JavaScript and never stored in `localStorage`.
5. **Record.** A success resets the (e-mail, IP) failure counter, writes the login history (§5) and the
   audit event `auth.login`.

## 4. Session use and sign-out

- Every merchant endpoint depends on `get_scope`: decode the cookie (401 when missing, invalid or
  expired), then `ResolveScope` picks the merchant **from the server-side grants**. An optional
  `X-Merchant-Id` header can only select among the user's own grants (403 otherwise). A client-supplied
  merchant id is never authorisation.
- Objects from another merchant (transaction, customer token, alert, report) answer **404**, never 403,
  so their existence isn't revealed.
- `POST /api/v1/auth/logout` records a `logout` event if the cookie is valid, then deletes the cookie.
  JWTs are stateless, so a copied token stays valid until `exp` *(gap: server-side revocation list
  or short-lived tokens with refresh)*.

## 5. Login history: `GET /api/v1/auth/history?limit=1..100`

Table `login_events (user_id, outcome, occurred_at, ip, user_agent)`, migration `8ab0d7911dc5`.

| Outcome | Recorded when |
|---|---|
| `success` | password verified, session issued |
| `failure` | wrong password on an **existing** account |
| `throttled` | attempt refused by the limiter, on an existing account |
| `logout` | sign-out with a valid session |

Rules:
- **Failures persist even though the request fails.** Events are written in their own short
  transaction (`SqlLoginHistory`), not the request's unit of work, which rolls back on 401.
- **Unknown e-mails are not stored.** The history must not become a list of probed addresses (they
  appear only in the throttle and in logs, which hold the IP and no e-mail).
- **Per user.** The endpoint uses the signed-in user id from the cookie. It is not merchant-scoped, so
  a user never sees anyone else's events, even on a shared merchant.
- **Minimal data.** IP (as seen by the API) and User-Agent truncated to 300 characters. The API returns
  only `device` = browser family · OS. Retention is **90 days**, pruned on each write.
- **Summary.** Failed + throttled attempts in the last 30 days, and the *previous* successful login
  (so the user can spot a sign-in that wasn't theirs). Shown in Settings → Sécurité du compte.

## 6. Authorisation matrix

| Action | owner | staff | anonymous |
|---|---|---|---|
| Read dashboards, ledger, collections, alerts, insights, customers, reports | ✅ | ✅ | 401 |
| Acknowledge or resolve alerts, record win-back decisions, run simulations | ✅ | ✅ | 401 |
| Edit merchant profile (`PATCH /merchant/me`) | ✅ | 403 | 401 |
| Save loyalty programme, run pilot accrual | ✅ | 403 | 401 |
| Own login history | ✅ (own) | ✅ (own) | 401 |

## 7. Transport and browser protections

- Security headers on every response: `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`,
  `Referrer-Policy: strict-origin-when-cross-origin`, `Permissions-Policy`, `Cross-Origin-Opener-Policy`,
  and `Content-Security-Policy: default-src 'none'; frame-ancestors 'none'` on JSON (Swagger UI exempt).
- CSRF: `SameSite=Lax` plus the Origin guard on POST/PUT/PATCH/DELETE; no state-changing GET exists. A
  cross-site page cannot forge `X-Forwarded-Host`: it isn't a CORS-safelisted header, so the browser
  preflights the request and the CORS allowlist refuses it.
- CORS: exact allowlist (`CORS_ORIGINS`) with credentials; no wildcard.
- TLS: required in any deployment, together with `COOKIE_SECURE=true` *(deployment responsibility)*.

## 8. Secrets and configuration

`JWT_SECRET` must be a long random value from the environment. The default in `config.py` is
dev-only and must never reach production *(gap: refuse to start in production with the default)*.
`.env` is git-ignored and `.env.example` holds placeholders only.

## 9. Audit trail (`audit_events`)

`auth.login`, `merchant.profile_updated` (field names only), `customer.decision` (masked token),
`loyalty.program_saved`, `loyalty.pilot_accrued`, `report.exported` (period and format, no figures).
Login failures and throttles live in `login_events` (§5), plus a log line with the IP for throttles.

## 10. Demo accounts (synthetic only, password `demo1234`)

`demo@ceo-pay.test` (owner, M-DEMO-01), `demo2@ceo-pay.test` (owner, M-DEMO-02), and
`owner@ceo-pay.test` (after a workbook import). If you lock yourself out (5 failures in 15 min):
`docker compose restart backend`.

## 11. Known gaps before real use

Self-registration with e-mail verification; password reset; MFA for owners; server-side session
revocation and "sign out everywhere"; a shared throttle store; refusing default secrets at startup;
trusted-proxy configuration so `login_events.ip` shows the client IP behind a reverse proxy.
