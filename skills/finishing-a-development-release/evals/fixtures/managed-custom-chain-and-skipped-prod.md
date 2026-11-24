# Release Snapshot

Repository: `example/crawler-platform` (Python web + worker + PostgreSQL service).
Target release: `v0.107.0`.
Git tags in history: `v0.104.0` (DB schema v11), `v0.105.0` (DB schema v12 & v13), `v0.106.0` (DB schema v13, no new migration).
User note: "准备发 v0.107.0；注意 v0.105.0 和 v0.106.0 虽然打过 tag，但生产环境目前实际还停在 v0.104.0（数据库 v11），请按生产实际起点准备好升级材料。"
Authorization: user authorized version release with deployment package.

## Repository Migration Mechanism
- No Flyway/Alembic/Prisma. The repository uses its own sequential Python migration chain in `server/storage/schema_migrations/`:
  - Records applied versions, checksums, and frozen catalog digests in `schema_version_history`.
  - Business startup checks schema version only and refuses mismatched DB versions.
  - Explicit upgrade command: `python scripts/manage_postgres.py upgrade --config <path> --expected-version <current_db_ver> --application-role <role>`.
  - Read-only status check command: `python scripts/manage_postgres.py status --config <path>`.
  - No downward DDL rollback; rollback requires stopping writes, exporting/preserving post-upgrade data, and restoring verified pre-upgrade backup with matching old app version.

## Version Diff (`v0.104.0..HEAD`)
- `server/storage/schema_migrations/v012_project_resources.py` (v0.105.0)
- `server/storage/schema_migrations/v013_collect_indexes.py` (v0.105.0)
- `server/storage/schema_migrations/v014_target_scope_summary.py` (v0.107.0)
- Web & Publisher app changes (v0.106.0 reason codes, v0.107.0 scope summary).
- All v012–v014 migrations have frozen checksums and digests; modifying or merging them breaks version verification.
