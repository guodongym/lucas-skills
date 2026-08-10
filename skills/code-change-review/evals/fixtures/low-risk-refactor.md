# Behavior-preserving local refactor

## Review scope

Review only commit range `8d17c20..91a44b2`. Direct unit tests ran 42/42 successfully after the change.

```diff
diff --git a/reporting/normalize.py b/reporting/normalize.py
@@ -8,5 +8,5 @@ def normalize(values):
-    rows = [value.strip().lower() for value in values]
-    return tuple(rows)
+    records = [value.strip().lower() for value in values]
+    return tuple(records)
```

The function is private, has no reflection-based consumers, and the commit is independently revertible.
