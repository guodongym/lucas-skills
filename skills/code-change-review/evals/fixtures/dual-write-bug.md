# Dual-write implementation

## Review scope

Review only the shown change in `payments/transfers.py` for defects and merge readiness. Do not edit files.

## Requirement and baseline

Moving credits between accounts and the transfer ledger is one business operation. Before this change, callers observed either all three records updated or none updated. Account existence and command deduplication are validated by unchanged caller code outside this fixture.

## Changed code

```diff
diff --git a/payments/transfers.py b/payments/transfers.py
@@ -20,6 +20,9 @@ def transfer(db, source_id, target_id, amount):
-    return db.call("transfer_credits", source_id, target_id, amount)
+    db.execute("UPDATE accounts SET credits = credits - ? WHERE id = ?", amount, source_id)
+    db.execute("UPDATE accounts SET credits = credits + ? WHERE id = ?", amount, target_id)
+    db.execute("INSERT INTO transfer_ledger(source_id, target_id, amount) VALUES (?, ?, ?)", source_id, target_id, amount)
+    return {"status": "completed"}
```

The database client autocommits `execute` calls outside a transaction. `db.transaction()` rolls back every statement when its block raises. The HTTP handler returns 503 when `transfer` raises. Existing tests cover only successful execution.
