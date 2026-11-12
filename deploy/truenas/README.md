# Deploy Touchline on TrueNAS SCALE with Tailscale Funnel

This deploys the web UI and API together in one container. SQLite lives on a
TrueNAS dataset, so app restarts and image updates do not erase club data.
The Funnel HTTPS URL is `https://truenas-scale.tail1da715.ts.net`.

## 1. Prepare two TrueNAS datasets

In **Storage → Datasets**, create these datasets under your app pool (replace
`POOL_NAME` with the pool shown in TrueNAS):

- `apps/touchline/source`
- `apps/touchline/data`

The first stores the app source used to build the container. The second stores
the SQLite database. Use a scheduled ZFS snapshot for the `data` dataset, and
keep a separate backup copy of that dataset.

## 2. Copy the source to the NAS

From the project directory on your Mac, create an archive containing only the
runtime source. It deliberately excludes `.env`, local databases, and native
build artifacts:

```sh
tar -czf touchline-source.tar.gz Dockerfile .dockerignore requirements.txt index.html styles.css backend js styles
```

Copy `touchline-source.tar.gz` into the TrueNAS `source` dataset using an SMB
share or SCP. In the TrueNAS Shell, extract it into that dataset, keeping the
files directly in the `source` directory (so `Dockerfile` is at its root).
For example, after adjusting the pool name and archive location:

```sh
tar -xzf /mnt/POOL_NAME/apps/touchline/source/touchline-source.tar.gz -C /mnt/POOL_NAME/apps/touchline/source
```

Delete the archive after extraction if desired. Do not copy your Mac `.env` or
`data/touchline.db` into the deployment source. This starts with a fresh,
empty database in the persistent TrueNAS data dataset.

## 3. Set database dataset permissions

In the TrueNAS ACL editor for `apps/touchline/data`, grant the `apps` user and
group (UID/GID `568`) read, write, and traverse access, and apply it to the
dataset. The container runs as that unprivileged user and needs write access
for SQLite and its WAL files. The source dataset only needs to be readable by
the Docker build service.

## 4. Configure the app secrets

Replace both occurrences of `POOL_NAME`. The Compose file reads administrator,
SMTP, 2FA, and optional Google OAuth credentials from environment variables.
Provide these through the secret/environment mechanism supported by your
TrueNAS SCALE release. If that release requires literal Compose values, make a
private deployment copy and never commit that filled copy. Keep the app base
URL exactly as:

```text
https://truenas-scale.tail1da715.ts.net
```

Generate a long random admin path and a Fernet encryption key locally:

```sh
python3 -c 'import secrets; print("/manage-" + secrets.token_urlsafe(32))'
python3 -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'
```

Set a unique admin password. For Gmail SMTP, use a Google App Password, not
your normal Google password. Keep the 2FA encryption key stable: changing it
later prevents existing authenticator secrets from being decrypted. Configure
these values before the first launch so the super-admin account is provisioned
correctly. Restrict access to the TrueNAS app environment where the secrets
are stored.

## 5. Install the Custom App

In TrueNAS, open **Apps → Discover Apps → ⋮ → Install via YAML**. Name the app
`touchline`, paste the completed `compose.yaml` contents, and save. TrueNAS
Custom Apps use Docker Compose YAML, and the current TrueNAS docs include
building a local image from a Dockerfile during app installation.

Wait for the app to report healthy. From the TrueNAS Shell, verify the local
service:

```sh
curl -fsS http://127.0.0.1:4173/api/v1/health
```

The container port is published only on host loopback so the Funnel can reach
it without making port 4173 directly reachable from the LAN or internet.

## 6. Point Funnel at Touchline

On the TrueNAS host, check the Funnel target:

```sh
tailscale funnel status
```

If it is not forwarding the HTTPS service to port 4173, configure the
persistent background Funnel target:

```sh
tailscale funnel --bg 4173
```

Check status again and confirm it shows the TrueNAS URL proxying to
`http://127.0.0.1:4173`. Funnel terminates HTTPS and proxies requests to the
local HTTP app; the same route carries both the frontend and `/api/v1` calls.

## 7. Verify sign-in and email

Open the public app at:

```text
https://truenas-scale.tail1da715.ts.net
```

Open the admin entry using the secret path configured in the Compose file,
then sign in with the configured admin email and password. Register a test
member and confirm that the verification email links back to this HTTPS host.
Also verify password reset and a 2FA setup before inviting other users.

The iOS and Android apps use the same backend. On each device, choose **Server
connection** on the sign-in screen and enter this origin (no `/api/v1` suffix):

```text
https://truenas-scale.tail1da715.ts.net
```

## 8. Backups and updates

- Schedule snapshots for `apps/touchline/data` and periodically copy backups
  to another device or cloud location.
- To update, copy the new runtime source into the source dataset and use
  **Apps → Touchline → Edit** to redeploy/rebuild the Custom App. Keep the data
  dataset mounted at `/data` and retain the same admin, SMTP, timezone, and 2FA
  environment values.
- Before a schema or code update, take a data snapshot. Roll back by redeploying
  the previous app image/source, or restoring a known-good database snapshot.

## Exposure and operational notes

Tailscale Funnel makes this URL reachable from the public internet; anyone with
the URL can load the sign-in and registration pages. Keep strong passwords and
email verification enabled, protect the private admin path, and do not publish
the Compose file or database. Funnel requires the node's Funnel policy and
HTTPS/MagicDNS setup, and its public bandwidth has Tailscale-defined limits.

If the app does not become healthy, check **Apps → Touchline → Logs** first.
Common issues are an incorrect pool path, data dataset ACLs not granting UID
568 write access, a missing secret replacement, or a Funnel still targeting a
different port.

## Google sign-in setup

Create a Google OAuth **Web application** client and register this authorized
redirect URI exactly:

```text
https://truenas-scale.tail1da715.ts.net/
```

Set `TOUCHLINE_GOOGLE_CLIENT_ID`, `TOUCHLINE_GOOGLE_CLIENT_SECRET`, and
`TOUCHLINE_GOOGLE_REDIRECT_URI` in the TrueNAS app environment. The sign-in
button stays hidden until both credentials are present. Keep the client secret
out of Git and chat. Web sign-in is implemented; native iOS and Android Google
sign-in needs their platform client IDs and native credential handoff before it
can be enabled in those apps.
