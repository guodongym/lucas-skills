# Release Snapshot

Repository: `example/order-gateway` (deployable Go HTTP gateway).
Target release: `v2.1.0`. Previous stable tag: `v2.0.0`.
Authorization: user requested version release `v2.1.0` (no explicit deployment-package override).

## Repository Rules (`AGENTS.md`)
- "Every released version MUST include a release deployment record under `deploy/releases/<version>/`."

## Version Diff (`v2.0.0..HEAD`)
1. `migrations/009_add_webhook_secret_id.sql` (added): `ALTER TABLE webhooks ADD COLUMN secret_id VARCHAR(64);` (uses managed `golang-migrate`).
2. `.env.example` (modified): added `WEBHOOK_SIGNING_SECRET_ID=` and `WEBHOOK_TIMEOUT_MS=5000`.
3. `deploy/docker-compose.yml` (modified): exposes new health endpoint check and mounts `/etc/gateway/certs:ro`.
4. `cmd/gateway/main.go` (modified): requires `WEBHOOK_SIGNING_SECRET_ID` at startup; refuses to start if unset.
