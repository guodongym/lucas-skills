# Tenant scope implementation

## Review scope

Review only the shown change in `api/export.py` for defects and merge readiness. Do not edit files.

## Requirement and baseline

The tenant from gateway claims is authoritative. Request JSON may contain filters but must never select another tenant.

## Changed code

```diff
diff --git a/api/export.py b/api/export.py
@@ -31,7 +31,9 @@ def export_report(request):
-    tenant_id = request.context.claims["tenant_id"]
-    filters = parse_filters(request.json)
+    filters = parse_filters(request.json)
+    scope = {**filters, **request.context.claims}
+    tenant_id = scope["tenant_id"]
     authorize_export(request.context.user_id, tenant_id)
-    return reports.export(tenant_id=tenant_id, filters=filters)
+    return reports.export(tenant_id=tenant_id, filters=scope)
```

Authenticated clients control the JSON body, and `parse_filters` preserves a supported `tenant_id`. `authorize_export` checks export permission but assumes the tenant came from trusted claims. `reports.export` expects the merged scope and ignores non-filter claim keys. Tests use no `tenant_id` filter. The fixture does not establish broad exposure or irreversible disclosure.
