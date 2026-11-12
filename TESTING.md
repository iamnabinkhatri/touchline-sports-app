# Testing & security report

This report covers the full-stack Touchline build: browser client, Python API server, SQLite database and the integration between them.

## Scope

- Browser app served by the Python server.
- REST API under `/api/v1`.
- SQLite database at `data/touchline.db`.
- Token auth, role checks, SQL queries, static file serving, CSP and request validation.
- The web UI against the running API, plus direct API clients simulating mobile consumers.

## How to run

```bash
npm test                 # all frontend + backend tests
npm run test:frontend    # 42 Node tests
npm run test:backend     # 55 Python tests
npm run test:coverage    # frontend coverage report
```

Backend test commands use a 1,000-iteration PBKDF2 work factor for speed. Production defaults to 180,000 iterations.

## i. Unit testing

### Frontend — 42 tests

| Area | Coverage |
| --- | --- |
| `js/balance.js` | Equal splits, rating gap, goalkeeper split, odd-pool floater, empty/tiny pools, deterministic seed, doubtful players |
| `tests/fixtures/demo-state.js` | Test-only fixture for data-shape and render tests; never loaded by the web app |
| `js/utils.js` | HTML escaping, allowlisted class tokens, initials, clamp, pad, tones, countdown parsing |
| `js/views/*` | Rendering with hostile state, XSS/attribute-breakout payloads, SQLi-as-text rendering |
| `js/store.js` | Derived poll percentages, plan progress and availability grouping |
| CSP policy | No inline scripts in the shell, no `eval`/`new Function`/`document.write`, strict script source |
| API client | Centralized same-origin `/api/v1` access; no bypassing fetches |

Final result: **42/42 frontend tests pass**.

### Backend — 55 tests

| Area | Coverage |
| --- | --- |
| `backend/security.py` | Password hashing/verification, random and hashed tokens, session expiry, slug/initials |
| `backend/validation.py` | Text boundaries, integer/number validation, enums, email, password and option lists |
| `backend/balance.py` | Even/odd pools, strength gap, goalkeeper split, deterministic seed, empty pool |
| `backend/db.py` | Seed counts, foreign keys, SQLite persistence across connection reopen |
| `backend/server.py` + services | Health, OpenAPI, auth, roles, bootstrap, posts, comments, likes, polls, votes, communities, players, ratings, lineup, plans, checklist, notifications, pickup, schedule, demo reset |
| `backend/tests/test_api.py` | 34 HTTP integration tests, including concurrent reads/writes, expiry and authorization |
| `backend/tests/test_persistence.py` | Data and session survive a full server restart |
| `backend/tests/test_units.py` | Security, validation, balancing and database unit tests |
| `backend/tests/test_ratelimit.py` | Sliding-window limiter unit tests + HTTP lockout tests (per-account, per-IP spraying, registration flood, `Retry-After`, spoofed `X-Forwarded-For`) |

Final result: **55/55 backend tests pass**.

## ii. TDD approach

The testing loop was test-first where it mattered:

1. Frontend rating and security helpers were written from failing tests first in the earlier browser-only build.
2. For the backend, the API test suite was written before integration validation. The first complete HTTP run found a real failure: a newly added player had an aggregate row with `SUM(value) = NULL`, causing the serializer to throw `TypeError` (500). The serializer was fixed to treat `NULL` as `0`, and the full API suite was rerun.
3. The plan-date path was hardened after discovering that malformed ISO dates raised an uncaught `ValueError`; invalid dates now return a clean `400`.
4. The CORS layer was tested with allowed, same-origin/alternate-port and hostile origins. Same-origin requests on a changed port were initially rejected; that was fixed with a host-aware same-origin allowance.
5. Browser E2E exposed a frontend synchronization bug: the API store refreshed, but the app-level state still rendered the previous snapshot. The app now applies every new bootstrap snapshot before rendering.
6. A concurrency test exposed connection resets under parallel static module loads. The server listen backlog was raised and broken-pipe logging was handled.

Baseline failure counts and the final green runs are shown in the loop table below.

## iii. SQL injection testing

This app now has a real SQLite database, so SQL injection is applicable. All SQL uses parameterized placeholders; no request value is concatenated into a query.

Tested payloads:

```text
' OR 1=1; DROP TABLE posts; --
" UNION SELECT username, password FROM users --
```

Coverage:

- Payloads submitted through post, comment, community, poll, player and plan forms.
- Payloads persisted and returned through the API.
- The `posts` table still existed and accepted writes afterward.
- Community search/filter parameters and dynamic path IDs remain parameterized.
- API tests verify no SQL driver dependency exists outside SQLite and no SQL is executed from the browser.

Result: **all injection payloads remained inert text**.

## iv. Penetration testing

### Backend attack surface

- Token theft/forgery and expired/invalid sessions.
- Password verification and stored hash inspection.
- Authorization boundaries (member vs admin/coach).
- Header, CORS and preflight handling.
- Path traversal, encoded traversal, dotfiles and source-file exposure.
- Method abuse and request-body limits.
- Malformed JSON and wrong content types.
- SQL injection.
- Stored XSS through API data rendered in the browser.
- Concurrent reads and writes.
- Data/session persistence across server restarts.
- Demo reset and session invalidation.

### Findings and fixes

| Severity | Finding | Fix |
| --- | --- | --- |
| High | Frontend state could remain stale after a mutation because the API store refreshed but the app-level variable did not | Assign every bootstrap snapshot to the app state before rendering |
| Medium | New player serializer crashed on `SUM(value) = NULL` | Treat missing aggregates as zero |
| Medium | Malformed plan dates could produce a 500 | Parse/validate dates and return `400 invalid_field` |
| Medium | CORS rejected same-origin requests when the local port changed | Allow the request host as same-origin while keeping the explicit allowlist |
| Medium | Parallel static module loads occasionally reset connections | HTTP/1.1, larger listen backlog and broken-pipe handling |
| Medium | Browser-only data model had no server-side authorization | Server roles for player/team/plan management; Bearer sessions |
| Medium | No server-side SQL | Added SQLite with parameterized queries and SQL injection tests |
| Low | Source files could be downloaded | Block `backend/`, `data/`, `tests/`, README/config files from static serving |
| Low | No body size limit | 256 KB JSON body cap, `413` response |
| Low | Unhashed session tokens | Store only SHA-256 token hashes |
| Medium | No login throttling: 25 consecutive wrong passwords were all evaluated (brute force / credential stuffing) | Sliding-window limiter: 5 failures per account and 20 per IP per 5 min, 20 registrations per IP per hour; `429` + `Retry-After`; successful login clears the account counter |
| Low | Unknown emails returned faster than wrong passwords (timing user enumeration) | Unknown-email path now runs a dummy PBKDF2 verification |
| Info | `npm run test:frontend` failed on Node 22 (`node --test tests` treats the folder as a module) | Scripts now pass `tests/*.test.mjs` |
| Info | No cache headers | `Cache-Control: no-store` on all responses |

### Authentication and authorization

- Passwords are salted PBKDF2-SHA256; the database never contains plaintext passwords.
- Session tokens are 256-bit random values; only their hashes are stored.
- Sessions expire after 30 days and are checked on every private request.
- Members cannot add/update players, edit the team sheet or create plans.
- Admin-only demo reset drops all data and issues a fresh token.
- CSRF is not applicable to the API because it uses Bearer headers, not cookies.

### Security headers

The Python server sends:

- `Content-Security-Policy` with `script-src 'self'`, `object-src 'none'`, `frame-ancestors 'none'`, `base-uri 'none'`, `form-action 'self'`.
- `X-Frame-Options: DENY`
- `X-Content-Type-Options: nosniff`
- `Referrer-Policy: no-referrer`
- `Permissions-Policy` disabling camera/microphone/geolocation/payment
- COOP/CORP and `X-Permitted-Cross-Domain-Policies: none`
- `Cache-Control: no-store`

### Browser E2E loop

| Run | Result |
| --- | --- |
| Core API-backed UI flow: boot, post, comment, poll, community, player, rating, plan, notifications, persistence | **16/16 passed** |
| Team/lineup formation, publish, join community, notifications, profile reset, mobile | **7/7 passed** |
| XSS/SQLi/token-recovery security run | **11/11 passed** |
| Pickup page, rating from API, doubtful/position toggles | **6/6 passed** |
| Route sweep: home, communities, polls, teams, pickup, plans | **6/6 pages loaded, 0 exceptions** |

The browser run confirmed no XSS execution, no CSP violations, no runtime exceptions and no horizontal overflow at mobile width.

## v. Fix-and-repeat loop

| Loop | Result |
| --- | --- |
| Browser-only baseline | 28 passing / 13 failing; rendering and token-class issues found |
| Browser-only hardened | 59/59 automated tests; 64/64 browser checks |
| Full-stack baseline | 28 API tests initially, 3 failures; aggregate/date handling and test assumptions corrected |
| Final full-stack | **42 frontend + 55 backend = 97/97 automated tests**, **40/40 browser checks**, 0 runtime/CSP failures |

## Residual risks (accepted)

- Rate limiting is in-memory and per-process (resets on restart; not shared across instances). Enforce the same limits at the proxy/gateway or back it with Redis when scaling out. Behind a reverse proxy set `TOUCHLINE_TRUST_PROXY=1` so the real client IP is used.
- `register` still returns `409 email_exists`, which reveals whether an email is registered (standard trade-off; mitigated by the registration limiter).
- No email verification, password reset, refresh tokens or “revoke all sessions” flow yet.
- Demo mode auto-login is enabled by default for the preview. Set `TOUCHLINE_DEMO_MODE=0` in production.
- SQLite is a single-node database; for horizontal scale, migrate to PostgreSQL and keep the same service layer contract.
- `style-src 'unsafe-inline'` is required by dynamic inline width/position styles; markup injection is mitigated by escaping and class allowlists.
- TLS is not terminated by the Python server. Use HTTPS at a reverse proxy for mobile/public access.
- Backups are not scheduled for `data/touchline.db`; add a backup rotation before production.

## Duties, calendar and penetration testing

| Suite | Command | Tests | What it covers |
| --- | --- | --- | --- |
| Duty and calendar behaviour | `npm run test:backend` (`test_calendar.py`) | 27 | Creating, claiming, releasing and deleting duties, the daily cap, the calendar merge and range rules, bootstrap, auth, OpenAPI. Includes **12 simultaneous claims** and **6 simultaneous claims against the daily cap**. |
| Security regression | `npm run test:backend` (`test_security.py`) | 27 | SQL injection on every duty and calendar input, stored script payloads, privilege escalation through registration and mass assignment, method override, path tricks, token handling, JSON bombs, content-type confusion, CORS, headers, error disclosure, and raw-socket request smuggling. |
| Calendar logic | `npm run test:frontend` (`calendar-model.test.mjs`) | 10 | Month grid, month navigation, local day grouping, claim states, the daily count, sorting. |
| Calendar rendering security | `npm run test:frontend` (`render-security.test.mjs`) | 4 | Hostile titles, notes and claimer names escaped in the calendar and the add-duty form. |
| Browser flow | `python3 tests/e2e/calendar_flow.py` (needs Playwright) | 16 | Browse months, claim and give back a duty, add and delete a duty, phone layout with a single row of navigation, no JavaScript errors. |
| Penetration test | `python3 pentest/pentest.py` | 42 (39 pass, 3 operator notes) | Black-box attacks over real sockets. Writes `pentest/PENTEST-REPORT.md`. |

Running `npm test` covers the unit and integration suites: 61 frontend and 132 backend tests.
