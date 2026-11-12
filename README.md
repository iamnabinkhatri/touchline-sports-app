# Touchline

Touchline is a full-stack sports clubhouse for soccer teams. It combines a community feed, soccer polls, player ratings, team management, an interactive starting XI, balanced pickup teams, and matchday game plans.

The current build uses a **Python API server + SQLite database**, so every change is stored on the server instead of in the browser. The same REST API is ready for future iOS and Android clients.

## Stack

- **Frontend:** plain HTML, CSS and ES modules (no build step).
- **Backend:** Python 3.9+ HTTP server (no third-party web framework); `cryptography` encrypts 2FA secrets.
- **Database:** SQLite with foreign keys, WAL mode and parameterized queries. New installs start with empty tables.
- **Auth:** opaque Bearer session tokens, stored as SHA-256 hashes; passwords use PBKDF2-SHA256.
- **API:** versioned REST API under `/api/v1`, documented with OpenAPI 3.0.

## Run it

```bash
python3 -m pip install -r requirements.txt
npm start
```

This starts the Python API + web server at [http://127.0.0.1:4173](http://127.0.0.1:4173).

The first start creates an empty `data/touchline.db`. The app has player sign-in and registration at `/`; the super-admin uses a separate private URL configured through environment variables.

### First launch

Set `TOUCHLINE_ADMIN_PATH`, `TOUCHLINE_ADMIN_EMAIL`, and `TOUCHLINE_ADMIN_PASSWORD` before starting the server. On startup, it creates the configured super-admin account; if that email already belongs to a member account, it promotes that account, sets the configured password, verifies the email, and revokes existing sessions. Open the private path, sign in, then create your club team or community. Community creation does not add a starter poll unless you choose it.

Member registration requires SMTP so the app can verify email addresses. Password reset also uses SMTP. For local testing, copy `.env.example` to `.env`, fill in the admin credentials/private path, SMTP values, and a generated `TOUCHLINE_2FA_ENCRYPTION_KEY`, then restart the server. The `.env` file is ignored by Git; keep the 2FA key stable so existing authenticator setups remain readable.

```bash
export TOUCHLINE_ADMIN_PATH="/manage-REPLACE-WITH-A-LONG-RANDOM-SECRET"
export TOUCHLINE_ADMIN_NAME="Your Name"
export TOUCHLINE_ADMIN_EMAIL="you@example.com"
export TOUCHLINE_ADMIN_PASSWORD="use-a-unique-long-password"
npm start
```

Open `http://127.0.0.1:4173/manage-REPLACE-WITH-A-LONG-RANDOM-SECRET`. The private path is an extra privacy layer; email and password are still required.

Run the raw server directly with:

```bash
python3 -m backend.server
```

There is no demo reset endpoint. Back up your SQLite file before any manual reset.

## API for mobile apps

- API base: `http://127.0.0.1:4173/api/v1`
- OpenAPI JSON: `http://127.0.0.1:4173/api/v1/openapi.json`
- Health: `GET /api/v1/health`
- Full guide: [API.md](API.md)

Mobile clients use `/api/v1/auth/login` or `/api/v1/auth/register`, then pass the returned token as a Bearer token to `/api/v1/bootstrap`.
Registration returns a verification-required response without a session token. Login can return a 2FA challenge before issuing the session token.

The API includes auth, bootstrap sync, feed posts/comments/likes, communities, polls and voting, player management and 1–10 ratings, lineup updates, game plans and checklist updates, notifications, schedule, and server-side pickup-team balancing.

For local network/mobile testing:

```bash
HOST=0.0.0.0 python3 -m backend.server
```

Then point the mobile client at `http://<your-computer-ip>:4173/api/v1`. Use HTTPS and a reverse proxy for a public deployment.

## iOS and Android apps

The Capacitor app packages the same responsive interface and uses the same `/api/v1` API and database as the browser app. Prepare the bundle with `npm run mobile:prepare`, generate the platform projects with `npm run mobile:add:ios` and `npm run mobile:add:android`, then follow [MOBILE.md](MOBILE.md) to connect, run, and build the apps.

## Features

### Communities
- Create public or private sports communities.
- Join communities and filter the clubhouse feed.
- New communities can start with a welcome poll.

### Soccer polls
- Vote and change votes; results and time-based closing.
- Create polls with 2–4 options and deadlines.
- Polls are embedded in the clubhouse feed.

### Team hub
- Server-backed roster, availability, player profiles and 1–10 ratings.
- Rate a player; the server keeps the rating average, count and your own vote.
- Add/update players and manage availability.
- Interactive starting XI with 4-3-3, 4-2-3-1 and 3-5-2; saves to the server.
- Auto-pick and publish the starting XI.

### Pickup builder
- Splits the available squad into two balanced teams by strength and position.
- Toggle doubtful players and position awareness, shuffle for another optimal split.
- Shows strength totals, positional make-up, captains, a balance score and a floater for odd pools.
- `GET /api/v1/pickup/teams` exposes the same calculation to mobile clients.

### Game plans
- Server-stored plan library, tactical phases, set pieces and checklists.
- Create matchday plans and toggle checklist progress.
- Copy a match brief for the group chat.

### Clubhouse
- Search, notifications, comments, likes, member profile, responsive layouts and accessible dialogs.
- New clubs and communities are created from the app; new community setup adds no sample poll unless selected.

## Data model

SQLite tables:

`users`, `sessions`, `communities`, `community_members`, `posts`, `post_likes`, `comments`, `polls`, `poll_options`, `poll_votes`, `teams`, `players`, `player_ratings`, `plans`, `notifications`, `events`, `fixtures`.

The database schema is in `backend/schema.sql`. New databases start empty; no sample clubs, players, posts, polls, plans or schedules are inserted.

The browser no longer stores club data in `localStorage`; it stores only the session token under `touchline:session`.

## Testing

```bash
npm test              # frontend Node tests + backend Python tests
npm run test:frontend # 42 frontend tests
npm run test:backend  # 55 backend API, unit, rate-limit and persistence tests
npm run test:coverage # frontend coverage report
```

The backend suite covers auth, password/token hashing, authorization roles, CRUD modules, SQL injection, login throttling, concurrent writes, CORS, security headers, path traversal, request limits, validation and persistence across a server restart. The browser E2E loop covers the complete UI against the API.

See [TESTING.md](TESTING.md) for the test report and security findings.

## Project structure

```
index.html
styles.css
js/                         # browser app, views and API client
backend/
  server.py                 # API routes + static web server
  service.py                # business operations
  serializers.py            # API response shapes
  db.py                     # SQLite connection and empty schema initialization
  schema.sql
  security.py               # password hashing, tokens and IDs
  balance.py                # server-side pickup balancing
  openapi.py
  tests/
data/touchline.db           # created at runtime
tests/                      # frontend Node tests
API.md
TESTING.md
```

## Configuration

See [API.md](API.md#configuration) for server settings and super-admin credentials.

## Security notes

- SQLite queries use placeholders; user input is never concatenated into SQL.
- Passwords use salted PBKDF2-SHA256; tokens are opaque and stored hashed.
- Role checks protect coach/admin operations.
- Strict CSP, frame protection, MIME sniffing protection, referrer policy and permissions policy are served by the Python server.
- Login/registration are rate limited (429 + `Retry-After`); JSON request bodies are limited to 256 KB.
- The local server binds to `127.0.0.1` by default. Put it behind HTTPS before exposing it to mobile devices or the internet.

## Security testing

Run the black-box penetration test against a fresh, throwaway server:

    python3 pentest/pentest.py

It writes `pentest/PENTEST-REPORT.md`. The script is an automated check, not a replacement for a human penetration test of your production deployment. Before going live, keep demo sign-in disabled, serve the app over HTTPS and send `Strict-Transport-Security` from your proxy. The private admin path does not replace strong credentials.
# touchline-sports-app
# touchline-sports-app
