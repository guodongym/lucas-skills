# Repository snapshot

Complete offline artifacts for example/billing PR #512 "feat(billing): 发票抬头独立成表". Base 3333333333333333333333333333333333333333; head 4444444444444444444444444444444444444444. No WIP. Locations use target-file coordinates. Supplied checks are author-run, not reviewer-run.

## Requirement and baseline

Approved spec `docs/specs/invoice-titles.md` (owner approval 2026-11-10, unchanged in this PR):

- Move the free-text `customers.invoice_title` into a new `invoice_titles` table (`customer_id`, `title`, `tax_id`, `is_default`).
- Migration 0057 backfills each customer's existing title as the default row.
- Creating or updating a title must validate `tax_id` and require `billing:write`.
- Reads switch to the new table in the same release. The old column stays for one release and is no longer written; rollback runs 0057's reverse, which copies default titles back into the old column.
- §4: "迁移、读切换、写校验必须同一版本上线，否则旧列与新表会出现分叉。"

Repository rule `docs/contributing.md:30` (unchanged): a PR whose core logic exceeds 800 hand-written lines must state in its description why it cannot be split.

## PR description and discussion

- Description: "不可拆原因：迁移、读切换与写校验必须同版本上线，否则新旧数据分叉（见 spec §4）。"
- Author note: "这个分支写了 3 天，开了一周，体量比较大。"
- Teammate comment (not the owner): "太大了，建议拆成迁移、读、写三个 PR。"

## Diff stat (core 890 added / 988 changed hand-written lines, tests 620)

| File | Change |
| --- | --- |
| `migrations/0057_invoice_titles.py` | +142 (new; forward creates table and unique index on `(customer_id) where is_default`, backfills in batches of 1,000 with upsert on that index; reverse copies defaults back) |
| `backend/billing/titles_repository.py` | +264 (new) |
| `backend/billing/api.py` | +176 -58 (read/write endpoints switched to repository) |
| `backend/billing/validators.py` | +94 (new; tax id format and checksum) |
| `backend/billing/permissions.py` | +12 (`billing:write` on create/update) |
| `frontend/src/pages/billing/InvoiceTitleForm.tsx` | +202 -40 (multiple titles, default switch, field errors) |
| `tests/**` | +620 |

## Key code

`backend/billing/api.py` write path at head:
```python
@route("POST", "/customers/{customer_id}/invoice-titles")
def create_title(request, customer_id):
    require(request.user, "billing:write", customer_id)
    data = validators.invoice_title(request.json)   # raises 422 on bad tax_id
    return titles_repository.create(customer_id, data)
```
Every read of an invoice title in `backend/billing/**` and the invoice PDF renderer now goes through `titles_repository.get_default(customer_id)`; `rg "invoice_title\b" backend` at head finds only the migration.

## Author checks

Forward and reverse migration on a staging snapshot of 1.2M customers: forward 6m12s, reverse 4m40s, row counts equal. pytest 312/312, frontend unit 48/48.
