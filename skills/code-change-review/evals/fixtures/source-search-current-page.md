# Repository snapshot

Complete offline artifacts for example/sources PR #41. Base 1111111111111111111111111111111111111111; head 2222222222222222222222222222222222222222; no WIP. Locations use target-file coordinates.

Owner requirement R-8: entering a handle must find the corresponding account anywhere in the active owner's list. The owner has 60 rows ordered by id. Row 48 has handle `winterbird`; rows 1-20 do not contain that text. Initial page is 1 and pageSize is 20.

Existing api/sources.py:10:
```python
def list_sources(owner, page, page_size):
    return db.query("SELECT id, handle FROM sources WHERE owner_id = ? ORDER BY id LIMIT ? OFFSET ?", (owner, page_size, (page - 1) * page_size))
```
Sources.tsx:20 requests only page/pageSize and stores the response in `accounts`. There is no full-list cache or second request. The API has no search parameter. Other routes and callers are unchanged.

Head Sources.tsx:30:
```diff
- const visible = accounts;
+ const visible = accounts.filter(a => a.handle.includes(search));
```
Head Sources.tsx:42 stores the search input locally; it does not refetch. The pagination total still comes from the unfiltered server count. No tests changed. No approved architectural rule specifies which layer must implement search. No test execution is supplied.
