# Release Snapshot

Repository: `example/quota-svc` (Java service using Flyway managed migrations in `db/migration/` with checksum verification).
Target release: `v1.1.0` (formal stable release).
Previous stable tag: `v1.0.0` (currently running in production).
Published prerelease tag in range: `v1.1.0-rc.1` (already released and deployed to test/staging environments; `DEPLOY.md` covers production upgrade from `v1.0.0` and notes test environment upgrade from `v1.1.0-rc.1`).
Authorization: user authorized full version release `v1.1.0` with ops deployment materials.

## Version Diff Summary Across Supported Upgrade Starting Points
- `git diff --name-status --find-renames v1.0.0..HEAD -- db/migration/`:
  - `A` `db/migration/V20261120__add_quota_rules.sql` (brand new relative to production baseline `v1.0.0`)
- `git diff --name-status --find-renames v1.1.0-rc.1..HEAD -- db/migration/`:
  - `M` `db/migration/V20261120__add_quota_rules.sql` (first published in `v1.1.0-rc.1`, then edited in place before `v1.1.0` to add a `UNIQUE` constraint)
- No Flyway repeatable (`R__`) mechanism or proven checksum-compatibility path exists for editing `V20261120__add_quota_rules.sql` on test environments that already applied `v1.1.0-rc.1`.
