# Repository snapshot

Review only these complete simulated artifacts. Repository example/app; base 1111111111111111111111111111111111111111; head 2222222222222222222222222222222222222222; no WIP. Locations below use target-file coordinates. Verification reported here is supplied evidence, not a command you have run.

## Approved baseline and independent decision
ADR-8 originally reserved invoice visibility writes for billing. Owner-approved D-21, recorded outside this PR before implementation, transfers only display visibility to reporting; payment state stays exclusively in billing. D-21 authorizes a dedicated billing_invoice_visibility table and requires scoped grants, a read adapter and rolling compatibility. Acceptance verifies old billing readers and new reporting writes agree.

## Head change
reporting/filter.py lines 20-22:
```python
def hide_invoice(invoice_id):
    visibility_store.set_hidden(invoice_id, True)
```
visibility_store writes only the new billing_invoice_visibility table (migration/005.sql lines 1-3: invoice_id PRIMARY KEY, hidden BOOLEAN NOT NULL DEFAULT FALSE). Reporting has table-specific grants only. Billing reads through the approved compatibility adapter; payment writes and source of truth remain unchanged. The migration has completed backfill and old/new reader, authorization and rollback checks at head. Reverting reporting restores billing ownership through the adapter. The migration requires coordinated rollout. The PR updates ADR-8 to cite the independently available D-21 approval. All changed paths are supplied above; no omitted decision is required.
