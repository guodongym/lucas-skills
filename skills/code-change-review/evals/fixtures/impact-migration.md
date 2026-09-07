# Repository snapshot

Review only these complete simulated artifacts. Repository example/app; base 1111111111111111111111111111111111111111; head 2222222222222222222222222222222222222222; no WIP. Locations below use target-file coordinates. Verification reported here is supplied evidence, not a command you have run.

## Approved request and baseline
Owner D-40 approves changing orders.external_ref TEXT to BIGINT for a current reconciliation contract, with a verified corpus of canonical decimal references: no leading zeros, every value within signed BIGINT range, and integer conversion preserves reference equality across API, worker and reconciler. The data preflight report covers all existing rows. The migration changes representation and cannot preserve leading zeros. All known consumers are enumerated: API, worker, reconciler; they are upgraded together under a maintenance window. Legacy clients are retired with supplied usage evidence.

## Changes and verification
migration/007.sql lines 1-2: ALTER TABLE orders ALTER COLUMN external_ref TYPE BIGINT USING external_ref::BIGINT;
api/contract.json line 12 changes external_ref from string to integer.
worker/lookup.py line 8 and reconcile.py line 15 use integer matching. Original textual references are archived in an independently restorable backup. Restore drill succeeds, but rollback requires restoring the database and stopping writes; rolling binary rollback alone is not supported. All contract, archive restore and reconciliation tests passed at head. No new table or feature; coordinated breaking contract and storage migration are explicitly approved.
