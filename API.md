# Touchline API

The Touchline web app and REST API are served by one small Python server, backed by SQLite. Install `requirements.txt` for encrypted 2FA secret storage.

- Web app: `http://127.0.0.1:4173/`
- API base: `http://127.0.0.1:4173/api/v1`
- OpenAPI 3.0 (requires a session or approved API key): `http://127.0.0.1:4173/api/v1/openapi.json`
- Health: `GET /api/v1/health` (public)

## Authentication

All private endpoints use Bearer tokens:

```http
Authorization: Bearer <token>
```

Create a session. New member registration returns `verificationRequired` and sends an email; it does not create a session. If two-factor authentication is enabled, login returns `twoFactorRequired` and `challengeToken` instead of a session token.

```bash
# normal login
curl -s -X POST http://127.0.0.1:4173/api/v1/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"email":"you@example.com","password":"your-password"}'

# register a new member
curl -s -X POST http://127.0.0.1:4173/api/v1/auth/register \
  -H 'Content-Type: application/json' \
  -d '{"name":"Mobile User","email":"mobile@example.com","password":"strong-password"}'
# For an emailed player invitation, also include "player_invite":"<token>".
```

Responses look like:

```json
{
  "ok": true,
  "data": {
    "token": "opaque-session-token",
    "user": { "id": "user-id", "name": "Your Name", "role": "Member" }
  }
}
```

Tokens are stored in the database as SHA-256 hashes, not plain text.

### Approved API keys

The first-party web app uses signed-in session tokens. External integrations can use an API key only after a super admin approves the user's request. In the app, open **Profile → API access** to request and claim a key; the super admin reviews requests under **Profile → API key requests**. The key is shown once, stored as a hash, and can be revoked from API access settings.

Send an approved key in the `X-API-Key` header over HTTPS. Keep it on a trusted server and out of browser code, source control, and logs. Health and account sign-in/registration/recovery endpoints remain public so the app can start sessions; community and other private data endpoints require either a signed-in session or an approved API key. API-key management itself requires a signed-in session.

```http
X-API-Key: tl_live_<approved-secret>
```

## Response contract

Successful response:

```json
{ "ok": true, "data": {} }
```

Error response:

```json
{
  "ok": false,
  "error": {
    "code": "invalid_field",
    "message": "Enter a valid email address.",
    "fields": { "email": "format" }
  }
}
```

Common status codes: `400` validation, `401` unauthenticated, `403` forbidden role, `404` missing resource, `409` conflict, `413` body too large, `415` wrong media type, `500` unexpected server error.

## Endpoints

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/api/v1/bootstrap` | Full state for the web client: user, communities, posts, polls, teams, plans, notifications, schedule, fixtures, leaders |
| GET | `/api/v1/me` | Current user |
| GET | `/api/v1/me/api-key` | View API-key request/credential status |
| POST | `/api/v1/me/api-key-requests` | Request super-admin approval for API access |
| POST | `/api/v1/me/api-key-claim` | Claim an approved API key (secret shown once) |
| DELETE | `/api/v1/me/api-key` | Revoke the active API key |
| GET | `/api/v1/admin/api-key-requests` | List pending requests (super admin only) |
| POST | `/api/v1/admin/api-key-requests/{id}/decision` | Approve or deny a request (super admin only) |
| POST | `/api/v1/auth/admin` | Super-admin sign-in (private URL in the web app) |
| POST | `/api/v1/auth/login` | Email/password login |
| POST | `/api/v1/auth/register` | Register a member |
| POST | `/api/v1/auth/verify-email` | Verify an email with its one-time link token |
| POST | `/api/v1/auth/verification/resend` | Resend verification email (generic response) |
| POST | `/api/v1/auth/password/forgot` | Request a reset email (generic response) |
| POST | `/api/v1/auth/password/reset` | Use a reset token and new password; revoke sessions |
| POST | `/api/v1/auth/password/change` | Change password with current password |
| POST | `/api/v1/auth/2fa/setup` | Start authenticator enrollment |
| POST | `/api/v1/auth/2fa/enable` | Confirm code and enable 2FA; returns one-time recovery codes |
| POST | `/api/v1/auth/2fa/login` | Complete a 2FA challenge with TOTP or recovery code |
| POST | `/api/v1/auth/2fa/disable` | Disable 2FA with password and current TOTP |
| POST | `/api/v1/auth/logout` | Revoke current session |
| GET | `/api/v1/posts?community_id=&tag=` | Feed |
| POST | `/api/v1/posts` | Create post |
| POST | `/api/v1/posts/{id}/like` | Toggle like |
| POST | `/api/v1/posts/{id}/comments` | Add comment |
| GET | `/api/v1/polls` | Polls |
| POST | `/api/v1/polls` | Create poll; Pickup is the default. Accepts `closes_at` as an exact ISO date/time. Pickup and Competition polls also require `community_id` and `game_at`; Pickup accepts optional `location`. |
| POST | `/api/v1/polls/{id}/vote` | Vote or change vote; Pickup polls accept only `Yes` or `No`. A `Yes` response must identify the authenticated member’s linked player profile (legacy profiles still match by account name) and accepts `guest_count` from 0–2. A player can only be registered once for that poll. |
| POST | `/api/v1/polls/{id}/teams` | Community admin or poll creator manually rearranges the balanced teams after close (`team_a`, `team_b`, optional `floater`) |
| GET | `/api/v1/polls/{id}/feedback` | Poll voter rating form; community admins also receive submitted rating results |
| POST | `/api/v1/polls/{id}/feedback` | Submit 1–10 ratings and optional comments for every active community player |
| GET | `/api/v1/communities/{id}/poll-retention-settings` | Read effective poll retention (community admin or super admin) |
| PATCH | `/api/v1/communities/{id}/poll-retention-settings` | Set this community’s retention to 1–30 days (community admin or super admin) |
| GET | `/api/v1/communities` | Communities |
| POST | `/api/v1/communities` | Create community |
| PATCH | `/api/v1/communities/{id}` | Set or clear the community logo and banner (community admin only) |
| POST | `/api/v1/communities/{id}/join` | Request to join a public community (admin approval required; super admin may enter directly) |
| POST | `/api/v1/communities/{id}/join-requests` | Submit or retry a public community join request |
| GET | `/api/v1/communities/{id}/join-requests` | List pending requests (community admin or super admin) |
| POST | `/api/v1/communities/{id}/join-requests/{user_id}/decision` | Approve or decline a request |
| GET | `/api/v1/communities/{id}/members` | List members and roles |
| POST | `/api/v1/communities/{id}/members` | Add an existing verified user by email (community admin only) |
| POST | `/api/v1/communities/{id}/invites` | Create a seven-day shareable invite URL (community admin only) |
| POST | `/api/v1/community-invites/accept` | Accept an invite using `{ "token": "..." }` |
| GET | `/api/v1/communities/{id}/deletion-request` | Get latest deletion request and admin approvals |
| POST | `/api/v1/communities/{id}/deletion-requests` | Request deletion (community admin only) |
| POST | `/api/v1/communities/{id}/deletion-requests/{request_id}/approve` | Record one community admin’s approval |
| GET | `/api/v1/admin/community-deletions` | Super-admin deletion panel and timeout setting |
| PATCH | `/api/v1/admin/community-deletion-settings` | Set auto-delete review window to 1–30 days (super admin only) |
| PATCH | `/api/v1/admin/poll-retention-settings` | Set default poll retention to 1–30 days (super admin only; default 7) |
| POST | `/api/v1/admin/community-deletions/{request_id}/decision` | Approve or deny (super admin only) |
| GET | `/api/v1/communities/{id}/messages` | List up to 100 member-only chat messages |
| POST | `/api/v1/communities/{id}/messages` | Send a member-only chat message (max 1,000 characters) |
| POST | `/api/v1/communities/{id}/fixtures/{fixture_id}/ratings/request` | After a completed fixture, email verified community members a sign-in link to the player rating form (community admin only) |
| GET | `/api/v1/communities/{id}/fixtures/{fixture_id}/ratings` | Get the fixture-specific rating form (community member only) |
| POST | `/api/v1/communities/{id}/fixtures/{fixture_id}/ratings` | Submit ratings and optional feedback for every roster player |
| GET | `/api/v1/team` | Team, roster and starting XI |

Polls are removed when their retention period expires. The global default is 7 days and can be changed by the super admin. Community admins can override that value for their own community. Polls with no votes are removed immediately when their voting period closes.
| POST | `/api/v1/teams` | Create the first club team (admin/coach) |
| PATCH | `/api/v1/teams/{id}` | Formation, Starting XI with player IDs or `null` for empty slots, publish (admin/coach) |
| GET | `/api/v1/players` | Players |
| POST | `/api/v1/players` | Add a registered player by required email, or send an account registration invitation if that email is new. Optional `xi_slot` assigns the new player to that Starting XI slot after registration; accepts editable season stat fields. |
| GET | `/api/v1/players/{id}` | Player profile |
| PATCH | `/api/v1/players/{id}` | Update player (admin/coach) |
| DELETE | `/api/v1/players/{id}` | Remove player and leave their Starting XI position empty; deletion is rejected if the roster would drop below 11. |
| POST | `/api/v1/players/{id}/ratings` | Rate 1–10 |

Community creation accepts optional `logo_data` and `banner_data`; player create/update accepts `image_data`. Each value must be a PNG, JPEG, or WebP base64 data URL, validated against its file signature and within the server’s image/body size limits. The browser resizes and compresses selected images before upload. Matchday ratings are separate from season ratings; members can revise their ratings by submitting the form again.
| GET | `/api/v1/plans` | Game plans |
| POST | `/api/v1/plans` | Create plan (admin/coach) |
| GET | `/api/v1/plans/{id}` | Plan detail |
| PATCH | `/api/v1/plans/{id}/checklist/{check_id}` | Toggle/set checklist item |
| GET | `/api/v1/notifications` | Current user’s notifications |
| POST | `/api/v1/notifications/read` | Mark all or selected read |
| GET | `/api/v1/pickup/teams?include_doubtful=&position_aware=&seed=` | Server-calculated balanced teams |
| GET | `/api/v1/schedule` | Events and fixtures |

## Mobile integration notes

1. Use `/auth/login` or `/auth/register` on the device, then send the returned token as `Authorization: Bearer <token>`.
2. Store the token in iOS Keychain or Android Keystore-backed secure storage.
3. Use the OpenAPI JSON to generate a client (for example with `openapi-generator`).
4. Call `/bootstrap` once after login/session restore.
5. Use the pickup endpoint for native team-builder screens; it returns `teamA`, `teamB`, `floater`, gap, position gap and balance score.
6. Use a server URL reachable from the device. For local network testing, run:

```bash
HOST=0.0.0.0 python3 -m backend.server
```

Then use `http://<your-computer-ip>:4173/api/v1` from the device. For production, terminate TLS at a reverse proxy and use HTTPS.

### CORS

CORS is allowlisted by `TOUCHLINE_CORS_ORIGINS`, with same-origin requests allowed automatically. Native mobile HTTP clients do not enforce browser CORS, but any future web client must be added to the allowlist.

## Configuration

Email verification and password recovery require SMTP. Configure these environment variables before starting the app:

For local development, run `cp .env.example .env`, edit `.env` with your provider values, save it, and restart `npm start`. The server loads `.env` from the project root; variables already exported by the shell take precedence. `.env` is excluded from Git. For deployments, set the same values in the provider's secret environment settings.

To verify SMTP configuration without sending a message, run `python3 -m backend.smtp_check` from the project root. It reports whether TLS/login succeeded or whether Gmail rejected the credentials.

| Variable | Purpose |
| --- | --- |
| `TOUCHLINE_APP_BASE_URL` | Public HTTPS URL used to build verification/reset links |
| `TOUCHLINE_SMTP_HOST`, `TOUCHLINE_SMTP_PORT`, `TOUCHLINE_SMTP_TIMEOUT` | SMTP server settings (defaults: port 587, timeout 30 seconds) |
| `TOUCHLINE_SMTP_USERNAME`, `TOUCHLINE_SMTP_PASSWORD` | SMTP credentials |
| `TOUCHLINE_SMTP_FROM` | Sender address |
| `TOUCHLINE_SMTP_STARTTLS` | Use STARTTLS (default on) |
| `TOUCHLINE_2FA_ENCRYPTION_KEY` | Fernet key used to encrypt authenticator secrets at rest |

Install the Python dependency with `python3 -m pip install -r requirements.txt`. Generate the 2FA key once and keep it private and stable across deployments:

```bash
python3 -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'
```

Do not commit credentials or encryption keys. Configure them in your deployment provider's secret environment settings.

| Environment variable | Default | Meaning |
| --- | --- | --- |
| `HOST` | `127.0.0.1` | Bind address |
| `PORT` | `4173` | HTTP port |
| `TOUCHLINE_DB` | `data/touchline.db` | SQLite database file |
| `TOUCHLINE_ADMIN_PATH` | unset | Private path serving the super-admin sign-in screen |
| `TOUCHLINE_ADMIN_NAME` | `Super Admin` | Display name for the first administrator |
| `TOUCHLINE_ADMIN_EMAIL` | unset | Email that provisions the first administrator |
| `TOUCHLINE_ADMIN_PASSWORD` | unset | Password that provisions the first administrator |
| `TOUCHLINE_SESSION_DAYS` | `30` | Session lifetime |
| `TOUCHLINE_MAX_BODY` | `262144` | Maximum JSON request body |
| `TOUCHLINE_CORS_ORIGINS` | local origins | Comma-separated allowlist |
| `TOUCHLINE_PBKDF2_ITERATIONS` | `180000` | Password hashing work factor |

## Database

SQLite schema lives in `backend/schema.sql`. New databases start empty; the server does not insert sample content. Set the super-admin environment variables before first startup to provision the initial administrator.

Main tables: `users`, `sessions`, `api_key_requests`, `api_keys`, `communities`, `community_members`, `community_join_requests`, `posts`, `post_likes`, `comments`, `polls`, `poll_options`, `poll_votes`, `teams`, `players`, `player_invites`, `player_match_appearances`, `player_ratings`, `matchday_rating_requests`, `matchday_player_ratings`, `plans`, `notifications`, `events`, `fixtures`.

Pickup polls always use `Yes` and `No` options. Members choosing `Yes` select their linked community player and may add up to two unregistered guests. Confirmed players and guests appear in the pickup builder and balanced team split; guests inherit their host player's position and rating but are not included in player rating forms. `No` responses are excluded from the roster, feedback form, email recipients, and appearance stats. After the scheduled game time, each confirmed player receives one appearance and 90 minutes; a unique poll/player record prevents duplicate updates. Admins can edit appearances, starts, minutes, goals, assists, clean sheets, and cards in the player profile. Pickup voters marked Yes receive a feedback email at 10:00 local time when kick-off is between 05:00 and 08:00; otherwise the email is scheduled for 22:00 on the game day. Set `TOUCHLINE_TIMEZONE` (IANA timezone, for example `America/New_York`) to choose the app's scheduling timezone. The scheduler runs in the Python server process, so at least one app instance must stay running for timed email delivery.

For production, back up the SQLite file, run with a persistent volume, and use a reverse proxy with HTTPS.

### Rate limiting

| Variable | Default | Meaning |
| --- | --- | --- |
| `TOUCHLINE_LOGIN_FAILS_PER_EMAIL` | `5` | Failed logins per account per window before `429` |
| `TOUCHLINE_LOGIN_FAILS_PER_IP` | `20` | Failed logins per client IP per window |
| `TOUCHLINE_LOGIN_WINDOW` | `300` | Login window in seconds |
| `TOUCHLINE_REGISTER_PER_IP` | `20` | Registration attempts per IP per window |
| `TOUCHLINE_REGISTER_WINDOW` | `3600` | Registration window in seconds |
| `TOUCHLINE_TRUST_PROXY` | `0` | Use the last `X-Forwarded-For` hop as client IP (only behind a trusted proxy) |

A throttled request returns `429` with `error.code = "rate_limited"` and a `Retry-After` header. Mobile clients should back off for that many seconds.

### Request field naming

Request bodies use `snake_case` (for example `community_id`, `text`); see `/api/v1/openapi.json` for exact schemas.

### Matchday duties and calendar

A duty is a matchday job such as bringing coffee, donuts, snacks or drinks. Duties belong to the club team and are visible to every member.

| Method | Path | Who | Notes |
| --- | --- | --- | --- |
| `GET` | `/api/v1/calendar?from=YYYY-MM-DD&to=YYYY-MM-DD` | any member | Matches, club events and duties in one sorted list. Defaults to the current month. Maximum 93 days. |
| `POST` | `/api/v1/duties` | any member | Body: `kind` (`coffee`, `donuts`, `snacks`, `drinks`, `other`), `starts_at` (ISO 8601), optional `title` (max 80), `note` (max 200), `event_key` (a fixture or event id). Limited to 30 per user per hour. |
| `POST` | `/api/v1/duties/{duty_id}/claim` | any member | First come, first served. `409 already_claimed` if taken. `409 claim_limit` after two duties on the same day. `409 duty_passed` after the match. |
| `DELETE` | `/api/v1/duties/{duty_id}/claim` | the person who took it, or a coach | Gives the duty back. |
| `DELETE` | `/api/v1/duties/{duty_id}` | the person who added it, or a coach | Removes the duty and any claim. |

Rules worth knowing when building clients:

- Claims are decided by a single conditional database update, so simultaneous requests cannot both win.
- The per-day limit and the 93-day calendar range are measured in UTC. Clients group entries by the viewer's local day.
- `GET /api/v1/bootstrap` includes `duties` for the last 24 hours and anything upcoming, so a client can render the calendar without a second call.
- Errors use the standard envelope. A `429` includes `Retry-After`.
