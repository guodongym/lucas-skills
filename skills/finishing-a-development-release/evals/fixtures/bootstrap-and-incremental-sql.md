# Release Snapshot

Repository: `example/service-alpha` (deployable Docker Compose web + worker service).
Target release: `v0.4.0`. Previous stable tag: `v0.3.0` (`1111111111111111111111111111111111111111`).
Current candidate commit on synced release branch: `2222222222222222222222222222222222222222`.
Authorization: user requested full version release to `main`, tag `v0.4.0`, and ops deployment materials for test/prod.

## Repository Conventions
- `deploy/README.md`:
  - `db/schema/dbinit.sql` is ONLY for initializing a brand-new empty database. Existing environments must NEVER run `dbinit.sql`.
  - Existing SQL archive directory is `db/schema/`. Existing environments apply applicable incremental `.sql` files from `db/schema/` in verified order.
  - `deploy/init.sh --force` is forbidden on existing environments because it overwrites manual vendor settings.
- `deploy/notes/provider-setup.md`:
  - `db/schema/20261110_add_provider_channel.sql` runs `ALTER TABLE accounts ADD COLUMN provider_channel VARCHAR(64)` and fails if the column already exists; ops must check `information_schema.columns` first and run it ONLY when `provider_channel` is absent.

## Version Diff (`v0.3.0..22222222`)
1. `db/schema/dbinit.sql` (modified): refreshed full empty-DB schema including all v0.4.0 tables/columns.
2. `db/schema/20261108_create_audit_events.sql` (added): `CREATE TABLE IF NOT EXISTS audit_events (...)`.
3. `db/schema/20261110_add_provider_channel.sql` (added): `ALTER TABLE accounts ADD COLUMN provider_channel VARCHAR(64);` (non-idempotent; requires column-absence precheck).
4. `db/schema/20261112_add_audit_idx.sql` (added): `CREATE INDEX idx_audit_events_created_at ON audit_events (created_at);` (depends on `audit_events` table existing).
5. `db/schema/20261114_seed_default_limits.sql` (added): `INSERT IGNORE INTO rate_limits (plan, rpm) VALUES ('standard', 120);` (independent of `audit_events` and `provider_channel`).
6. `.env.example` (modified): added `PROVIDER_API_ENDPOINT=https://api.provider.invalid` and `AUDIT_RETENTION_DAYS=90`. (PR notes mentioned `PROVIDER_API_ENDPOINT` only; `AUDIT_RETENTION_DAYS` was added in code/config diff without a PR note.)
7. `deploy/notes/pr-18-note.md` (added in PR #18): mentions setting `PROVIDER_API_ENDPOINT` and `OLD_DEBUG_FLAG=1`. In PR #21, `OLD_DEBUG_FLAG` was completely removed from code and `.env.example`.

## Local State
- `.env` exists locally (ignored) with real secret values; must not be printed or committed.
- No managed migration tool (no Flyway/Liquibase/Alembic/custom migration runner).
