# Retried external charge

## Review scope

Review only the shown change in `jobs/charge.py` for defects and merge readiness. Do not edit files.

## Requirement and baseline

A payment job may be delivered more than once, but one job must create at most one provider charge.

## Changed code

```diff
diff --git a/jobs/charge.py b/jobs/charge.py
@@ -40,7 +40,10 @@ def run_charge(job, provider, payments):
-    result = provider.create_charge(job.customer_id, job.amount, request_id=job.id)
+    result = provider.create_charge(
+        customer_id=job.customer_id,
+        amount=job.amount,
+        idempotency_key=job.id,
+    )
     payments.mark_paid(job.payment_id, result.charge_id)
```

The queue retries after timeout or crash. A timeout may occur after the provider accepts a charge but before `mark_paid`. The provider durably returns the original charge when an idempotency key is supplied and does not deduplicate calls without one. One job affects one customer; duplicate-charge reconciliation alerts within five minutes, and operators can refund a charge by its returned ID. These controls can bound and reverse a duplicate's impact but do not prevent a provider request. Tests mock one successful delivery.
