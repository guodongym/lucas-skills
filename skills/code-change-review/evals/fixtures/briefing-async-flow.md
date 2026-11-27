# Repository snapshot

Complete offline artifacts for example/shop PR #705 "feat(orders): 支付成功后改为异步开票". Base 9999999999999999999999999999999999999999; head aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa. No WIP. Locations use target-file coordinates. Supplied checks are author-run, not reviewer-run.

## Requirement and baseline

Owner issue #690 (approved): the payment callback calls the invoice service synchronously; P95 callback time is 4.8s and the payment platform retries callbacks after 3s, causing duplicate callbacks. Issue invoices asynchronously after the order is marked paid. An invoice failure must not fail the payment callback and must be visible to operators.

`InvoiceService` (external) accepts an `Idempotency-Key` header and returns the original invoice for a repeated key (vendor doc excerpt supplied by the author).

## Before

`PaymentCallbackHandler.handle` → mark order paid → `InvoiceClient.issue(order)` (synchronous) → respond 200.

## Head changes

| File | Change |
| --- | --- |
| `backend/payments/callback.py` | modified: in one DB transaction, marks the order paid and inserts `outbox(event="OrderPaid", order_id)`; the synchronous invoice call is removed |
| `migrations/0061_outbox.py` | new `outbox` table and `orders.invoice_status` (`pending`/`issued`/`failed`, default `pending`) |
| `backend/outbox/relay.py` | new; polls unsent outbox rows, publishes to queue `order-events`, marks rows sent after broker ack |
| `backend/invoices/worker.py` | new `InvoiceWorker`; consumes `OrderPaid`, calls `InvoiceClient.issue(order, idempotency_key=order_id)`, retries 3 times with backoff 2s/8s/30s, sets `invoice_status=issued` or `failed`, increments metric `invoice_failed_total` on failure, acks the message after the DB update, then calls `notifications.notify_invoice_ready(order_id)` on success |
| `backend/admin/orders.py` | shows `invoice_status` and a manual "重新开票" action that re-enqueues `OrderPaid` |
| `tests/**` | +410 |

`backend/notifications/` is not part of this PR and its source is not supplied; what `notify_invoice_ready` does is unknown.

## Author checks

pytest 221/221 (outbox written atomically with payment, relay retry after broker outage, worker idempotent replay, failure after 3 attempts sets `failed`). Staging callback P95 fell to 180ms.
