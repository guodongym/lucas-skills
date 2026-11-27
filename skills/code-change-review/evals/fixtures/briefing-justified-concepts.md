# Repository snapshot

Complete offline artifacts for example/notify PR #145 "fix(webhook): 临时失败后自动重试投递". Base dddddddddddddddddddddddddddddddddddddddd; head eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee. No WIP. Locations use target-file coordinates. Supplied checks are author-run, not reviewer-run.

## Requirement and baseline

The repository has no product or design documents; `AGENTS.md` only covers coding style and tests.

Owner issue #139 (approved): "客户的 webhook 端点偶尔返回 503 或超时，我们只投递一次就标记失败，客户因此丢事件。临时失败要自动重试几次，后台列表要能看出正在重试。"

Existing behavior: `deliveries.status` is `success` or `failed`; the admin list shows 成功 / 失败. Every delivery already sends header `X-Delivery-Id` (the delivery row id), documented in `docs/api/webhooks.md:30` as the receiver's de-duplication key.

## Head diff summary (6 files, +188 / -21)

| File | Change |
| --- | --- |
| `migrations/0044_delivery_retry.sql` | adds `deliveries.attempts INT NOT NULL DEFAULT 0` and `next_attempt_at TIMESTAMP NULL`; adds status value `retrying` |
| `backend/webhook/deliver.py` | on HTTP 5xx, 429 or timeout: `attempts += 1`; if `attempts >= 5`, set `status='failed'` and `next_attempt_at=NULL`, otherwise `status='retrying'` and `next_attempt_at = now + [1, 4, 16, 64][attempts-1]` minutes; 4xx other than 429 fails at once; same `X-Delivery-Id` on every attempt |
| `backend/webhook/scheduler.py` | existing 1-minute job now also picks `status='retrying' AND next_attempt_at <= now()` with `FOR UPDATE SKIP LOCKED`, limit 200 |
| `frontend/src/admin/DeliveryList.vue` | maps `retrying` to the label 重试中 next to the existing 成功 / 失败, using the existing `StatusTag` |
| tests | +96 (transient 503 then success, five failures → failed, 400 fails at once, two workers do not pick the same row) |

## Author checks

pytest 58/58, frontend unit 21/21.
