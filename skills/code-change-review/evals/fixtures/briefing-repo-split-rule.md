# Repository snapshot

Complete offline artifacts for example/platform PR #620 "feat(account): 账号停用与余额退款". Base 5555555555555555555555555555555555555555; head 6666666666666666666666666666666666666666. No WIP. Locations use target-file coordinates. Supplied checks are author-run, not reviewer-run.

## Requirement and baseline

Owner issue #600 (approved) lists two items that "can go live separately":

1. Admins can deactivate an account; all of its sessions are revoked immediately.
2. Operations can refund the remaining balance of a deactivated account through the payment gateway.

`accounts.status` with value `disabled` already exists (used by self-closure since migration 0031).

Repository rule `AGENTS.md:22` (mandatory, unchanged): "认证授权逻辑与计费/资金逻辑不得在同一 PR 中修改，须拆成顺序 PR 分别评审。"

## Diff stat

| File | Change |
| --- | --- |
| `backend/auth/deactivate.py` | +82 (new; requires `admin:accounts`, sets `status=disabled`, revokes sessions in one transaction) |
| `backend/billing/refund.py` | +141 (new; requires `billing:refund`, only for `disabled` accounts, calls `PaymentGateway.refund` with idempotency key `refund:{account_id}:{balance_version}`, records a ledger entry) |
| `backend/routes.py` | +28 (two new admin endpoints) |
| `tests/test_deactivate.py`, `tests/test_refund.py` | +264 |

The refund endpoint reads only `accounts.status`; it does not import or call `deactivate.py`. Deactivation does not touch balances.

## Author checks

pytest 188/188, including session revocation, permission denial, duplicate refund with the same key returning the original receipt, and gateway timeout leaving the refund `pending` for the existing reconciler.
