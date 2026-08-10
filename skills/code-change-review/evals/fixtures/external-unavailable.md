# External contract environment unavailable

## Review scope

Review commit range `ce410a0..df521b9` for defects and merge readiness.

```diff
diff --git a/client/parse_status.py b/client/parse_status.py
@@ -8,4 +8,4 @@ def parse_status(payload):
-    return payload["status"]
+    return payload.get("status", "pending")
```

Requirement: older external servers may omit `status`; missing status must map to `pending`. Direct unit tests cover present, absent, empty-string, and unknown values and pass 6/6. The external sandbox contract suite could not start because its credentials are unavailable. The sandbox failure occurred before any product request and changed no external state.
