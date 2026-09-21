# Repository snapshot

Complete offline artifacts for example/analytics PR #96. Base 1111111111111111111111111111111111111111; head 2222222222222222222222222222222222222222. No WIP. Locations use target-file coordinates. Supplied checks are not checks run by the reviewer.

## Requirement and baseline

Owner request R-12: make it possible to find a source account by handle or display name. Acceptance: find any matching account in the active owner/status scope and preserve the selected page size.

Pre-change DESIGN.md:40 requires the default trend view to show the account ranking alongside the trend. DESIGN.md:44 requires account detail to expose all native metrics, including the aggregate trend and numeric table. No independent decision replaces these requirements.

Integration guide:18 says interfaces supporting backend pagination must use it; no rule forbids every local filter. Other account lists use backend search/count/pagination. The sources API predates those lists; no owner count limit, volume measurements, or acceptance latency is supplied.

## Complete relevant API and call path (unchanged)

api/sources.py:10:
```python
def list_sources(owner_id, status):
    return db.query("SELECT handle, display_name FROM sources WHERE owner_id = ? AND status = ? ORDER BY handle", (owner_id, status))
```
This endpoint returns all rows in the requested scope. Sources.tsx:20 loads that response into `accounts`. No API page, limit or search parameter exists. Status and owner filters have not changed.

## Head diff

Sources.tsx:30:
```diff
- const visible = accounts.slice((page - 1) * pageSize, page * pageSize);
+ const matches = accounts.filter(a => `${a.handle} ${a.display_name}`.toLowerCase().includes(search.toLowerCase()));
+ const visible = matches.slice((page - 1) * pageSize, page * pageSize);
```
Sources.tsx:42 (onSearch; URL parameters supply page/pageSize with defaults 1/20):
```diff
+ setParams(new URLSearchParams({ status, search: value }));
```
Trend.tsx:70:
```diff
- <AccountRanking data={ranking} />
```
Ranking remains available in a separate view, reached by changing tabs.
Detail.tsx:90:
```diff
- const selected = showAll ? defs : defs.slice(0, 1);
- <Toggle checked={showAll} onChange={setShowAll}>All native metrics</Toggle>
+ const selected = defs.slice(0, 1);
```
Detail.tsx:100 and :110 both pass `selected` to the trend chart and numeric table. `defs` contains impressions, likes and replies. No other detail selector or aggregate metric view exists. A separate post inspector shows individual post observations. Persisted data is unchanged.

The author's new six-line note lists search and the two deletions as UI simplification. It supplies no observed problem with the charts, replacement acceptance or independent approval. The author reports the existing typecheck passed; no browser check is supplied. No dependency, schema or API diff exists.
