# Repository snapshot

Complete offline artifacts for example/picker PR #42. Base 1111111111111111111111111111111111111111; head 2222222222222222222222222222222222222222; no WIP. Locations use target-file coordinates.

Owner-approved R-9: filter an offline account picker by handle. Product capacity is 40 accounts per owner, enforced by the existing database write constraint on every insert/import path. The picker already loads all accounts and must work offline. No server-pagination requirement applies to this picker.

api/picker.py:10 returns all account handles for the authorized owner without LIMIT/OFFSET. Picker.tsx:20 caches the entire array before opening the picker. There are no other consumers or aggregate counts, and no paging controls.

Head Picker.tsx:30:
```diff
- const visible = accounts;
+ const visible = accounts.filter(a => a.handle.toLowerCase().includes(search.trim().toLowerCase()));
```
The search input stores a local string. No URL state, schema, API, other behavior or dependency changes.

Supplied checked evidence for this head: picker tests cover empty input, mixed case, whitespace, zero matches and the 40th account; all five passed. The complete shown path establishes a bounded scan over the full picker dataset. These are supplied results, not commands run by the reviewer.
