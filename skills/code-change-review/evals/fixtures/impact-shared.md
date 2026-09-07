# Repository snapshot

Review only these complete simulated artifacts. Repository example/app; base 1111111111111111111111111111111111111111; head 2222222222222222222222222222222222222222; no WIP. Locations below use target-file coordinates. Verification reported here is supplied evidence, not a command you have run.

## Independently approved requirement
R-50 changes the shared permission default: accounts without an explicit export grant must now be denied; previously they could export. Owner approved this tightened behavior for all API, worker and batch export paths. All three call can_export; no API signatures, database declarations or architectural boundaries change.

## Single-line change
security/permissions.py line 14:
```diff
- return grants.get("export", True)
+ return grants.get("export", False)
```
All entrypoints delegate authorization to this function and retain tenant binding. Baseline callers and tests are supplied: API, worker and batch export cover grant true, false and absent. All are updated to the owner-approved defaults and pass at head. Existing accounts without grants will lose access as intended; communication and rollback-to-old-default decision are approved.
