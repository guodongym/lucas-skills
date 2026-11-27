# Repository snapshot

Complete offline artifacts for example/shop PR #411 "feat(orders): 订单列表支持按渠道筛选". Base 1111111111111111111111111111111111111111; head 2222222222222222222222222222222222222222. No WIP. Locations use target-file coordinates. Supplied checks are author-run, not reviewer-run. The application cannot be started in this offline scenario.

## Requirement and baseline

Owner issue #398 (approved): operators need to filter the order list by order channel (`app`, `web`, `mini`). No other change was requested.

Repository rules (unchanged): AGENTS.md and docs/contributing.md contain no PR splitting or size rule. AGENTS.md:31 requires shared form components such as `FilterSelect` on list pages.

## Diff stat (134 files, +2,517 / -2,401)

| Files | Change |
| --- | --- |
| `backend/orders/api.py` | +4 -1 |
| `backend/orders/repository.py` | +2 |
| `frontend/src/pages/orders/OrderList.tsx` | +24 -4 |
| `tests/test_orders_filter.py` | +46 (new) |
| `frontend/web/OrderList.test.tsx` | +31 (new) |
| 112 files under `frontend/src/**` | +1,962 -1,962, Prettier 3 reformatting only |
| 14 files under `frontend/src/**` | +28 -28, rename `fmtDate` → `formatDate`, body unchanged |
| `.prettierrc`, `package.json` | +8 -4, Prettier 2.8.8 → 3.3.3 (devDependency), trailing-comma and quote options |
| `package-lock.json` | +412 -402 |

Author note: `git diff -w --ignore-blank-lines` over the 112 reformatted files leaves only quote and trailing-comma changes; the rename has no other references outside the 14 files (`rg fmtDate` empty at head).

## Key diffs

`backend/orders/api.py`:
```diff
@@ -20,5 +20,8 @@ def list_orders(request):
     page = parse_page(request)
+    channel = request.query.get("channel")
+    if channel is not None and channel not in {"app", "web", "mini"}:
+        raise BadRequest("invalid channel")
-    rows, total = repo.list_orders(tenant_id=request.tenant_id, page=page)
+    rows, total = repo.list_orders(tenant_id=request.tenant_id, page=page, channel=channel)
```

`backend/orders/repository.py`:
```diff
@@ -40,6 +40,8 @@ def list_orders(tenant_id, page, channel=None):
     q = Order.select().where(Order.tenant_id == tenant_id)
+    if channel is not None:
+        q = q.where(Order.channel == channel)
     total = q.count()
     rows = q.order_by(Order.created_at.desc()).paginate(page.number, page.size)
```

`orders.channel` already exists, is non-null and is indexed with `tenant_id` (migration 0042, unchanged). `list_orders` had a default `channel=None` before this PR and its only callers are `api.py:24` and an admin export that does not pass `channel`.

`OrderList.tsx` adds a `FilterSelect` with 全部/App/Web/小程序 bound to URL query `channel`; changing it resets the page to 1 and refetches. Empty results reuse the existing list empty state.

## Author checks

pytest 46/46 (each channel, invalid value → 400, tenant isolation, count equals filtered rows); frontend unit 12/12; `npm run lint` passed.
