# Repository snapshot

Review only these complete simulated artifacts. Repository example/app; base 1111111111111111111111111111111111111111; head 2222222222222222222222222222222222222222; no WIP. Locations below use target-file coordinates. Verification reported here is supplied evidence, not a command you have run.

## Approved baseline
ADR-8, approved before base: only billing service may write invoice state; reporting reads through BillingClient. A new UI filter must remain read-only. This boundary protects reconciliation ownership. No exception approved.

## Head change
reporting/filter.py lines 20-22 (added):
```python
def hide_invoice(invoice_id):
    db.execute("UPDATE billing_invoices SET hidden = TRUE WHERE id = ?", invoice_id)
```
The new report-filter route calls hide_invoice, and reporting is deployed with write grants to billing_invoices (deploy/reporting.yaml line 14). Only visibility changes, not money; all callers are authorized owners. This direct write is transactional and reversible; supplied tests prove the intended filter behavior. Existing BillingClient.set_visibility already performs the same update and is accessible to reporting. The author says direct SQL is simpler.
