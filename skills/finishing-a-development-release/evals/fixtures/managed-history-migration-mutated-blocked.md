# Release Snapshot

Repository: `example/ledger-api` (Java service using Flyway managed migrations in `db/migration/` with checksum verification).
Target release: `v3.2.0`. Previous stable tag: `v3.1.0` (already deployed to staging and production; Flyway recorded checksum of `V20261001__create_ledger_entries.sql` in `flyway_schema_history`).
Authorization: user authorized full version release `v3.2.0` with ops deployment materials.

## Version Diff Summary (`git diff --name-status v3.1.0..HEAD`)
- `M` `db/migration/V20261001__create_ledger_entries.sql` (an upstream feature PR edited this already-released migration in place to change `amount DECIMAL(12,2)` to `DECIMAL(16,4)`)
- `M` `src/main/java/com/example/ledger/Entry.java` (updated scale to 4)
- **Zero newly added (`A`) migration files** in `db/migration/`.
- No documented Flyway compatibility guarantee or repeatable (`R__`) mechanism applies to `V20261001__create_ledger_entries.sql`.
