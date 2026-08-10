# Commit range with unrelated working-tree WIP

## Requested scope

Review only commit range `ab410e1..bc521f8`; exclude all uncommitted work.

## In-range change

```diff
diff --git a/src/normalize.py b/src/normalize.py
@@ -14,4 +14,4 @@ def stable_values(values):
-    return [value for value in values]
+    return list(values)
```

Direct tests for `stable_values` pass 18/18 and observable behavior is unchanged.

## Current working-tree change, outside the requested range

```diff
diff --git a/src/debug_admin.py b/src/debug_admin.py
@@ -4,3 +4,3 @@ def can_access(user):
-    return user.is_admin
+    return True
```

The WIP is intentionally shown only so the reviewer can prove scope isolation. It must not become a finding for `ab410e1..bc521f8`.
