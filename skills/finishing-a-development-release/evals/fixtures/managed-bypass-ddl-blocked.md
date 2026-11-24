# Release Snapshot

Repository: `example/billing-api` (Python FastAPI service using Alembic managed migrations in `alembic/versions/`).
Target release: `v1.5.0`. Previous stable tag: `v1.4.0` (`aaaa1111aaaa1111aaaa1111aaaa1111aaaa1111`).
Candidate commit: `cccc3333cccc3333cccc3333cccc3333cccc3333`.
Authorization: user authorized full release (`main`, tag, deployment package).

## Repository Conventions
- Managed schema upgrades run exclusively via `alembic upgrade head`.

## Version Diff (`v1.4.0..cccc3333`)
1. `alembic/versions/20261115_01_add_invoice_memo.py` (added): adds nullable column `memo TEXT` to `invoices`.
2. `docs/pr-notes/pr-77-upgrade.sql` (added): PR #77 description instructs ops to run this SQL on existing test/prod databases during v1.5.0 upgrade:
   ```sql
   ALTER TABLE invoices ADD COLUMN tax_region VARCHAR(32) NOT NULL DEFAULT 'CN';
   CREATE INDEX idx_invoices_tax_region ON invoices (tax_region);
   ```
   There is NO corresponding Alembic revision for `tax_region`.
3. `src/billing/models.py` (modified): adds both `memo` and `tax_region` columns.
