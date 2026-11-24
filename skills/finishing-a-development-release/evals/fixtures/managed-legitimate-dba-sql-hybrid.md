# Release Snapshot

Repository: `example/analytics-api` (PostgreSQL + Flyway managed migrations in `db/migration/`).
Target release: `v2.3.0`. Previous stable tag: `v2.2.0`.
Authorization: user authorized full release with deployment materials.

## Repository Conventions
- Schema changes use Flyway (`flyway migrate`) running as limited migration role `app_migrator` inside a transaction.
- No custom archive directory for manual DBA scripts exists yet.

## Version Diff (`v2.2.0..HEAD`)
1. `db/migration/V20261118__add_vector_column.sql` (added): adds `embedding vector(1536)` column to `documents` (requires `pgvector` extension to exist first).
2. `docs/pr-92-dba-pre.sql` (added, PR #92 explicitly documents why Flyway cannot run it: `CREATE EXTENSION IF NOT EXISTS vector;` requires superuser privileges unavailable to `app_migrator` and must be executed by DBA BEFORE `flyway migrate`).
3. `docs/pr-95-dba-post.sql` (added, PR #95 documents non-transactional concurrent index creation that Flyway's default transactional runner cannot execute: `CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_documents_embedding ON documents USING hnsw (embedding vector_cosine_ops);`, must run AFTER `flyway migrate`).
4. No other `.sql` files changed.
