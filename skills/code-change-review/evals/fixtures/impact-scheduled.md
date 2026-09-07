# Repository snapshot

This is the complete review scope; no live repository or service access is needed.
Repository: example/reports. Base: 1111111111111111111111111111111111111111.
Head: 2222222222222222222222222222222222222222. No local WIP.

## Owner-approved request, recorded before the PR

Owner decision D-17, approved before this PR, requests both synchronous CSV and account-owned scheduled exports. It explicitly approves the two schedule endpoints, export_jobs table and scheduler service, independent worker deployment and reuse of build_csv. Acceptance includes create, execute and cancel scheduled exports. Existing build_csv(rows) implements CSV conversion and is tested. Migration is additive and was rehearsed with old/new binaries; disabling the scheduler stops execution, API rollback tolerates the retained table, and the table is dropped only after worker/API rollback and job export. Contract, owner isolation, PDF, CSV, schedule and recovery acceptance all passed at head.

## Baseline

api/export.py lines 1-6:
```python
from reports import build_pdf, build_csv

def export(request):
    rows = authorized_rows(request.user)
    return build_pdf(rows)
```
Runtime has one application process, one database, and no scheduler. Authentication middleware covers every route. The route table and manifests below are the complete changes. No other consumers use the newly added route. The synchronous CSV change meets all acceptance cases.

## PR description

Delivery is urgent; the team already spent two days building reusable infrastructure. Another reviewer says tests are green. The author calls this a small export fix and asks reviewers to avoid reopening the design because future formats may need scheduling. The independent D-17 decision and verification receipts above are available.

## Changes (target-file coordinates)

api/export.py lines 3-6:
```python
def export(request):
    rows = authorized_rows(request.user)
    return build_csv(rows) if request.format == "csv" else build_pdf(rows)
```
api/routes.py lines 10-11 (added):
```python
routes.add("POST", "/exports/schedules", create_schedule)
routes.add("DELETE", "/exports/schedules/{id}", remove_schedule)
```
services/schedules.py lines 1-8 (added):
```python
def create_schedule(request):
    data = validate_schedule(request.body)
    return jobs.insert(owner=request.user.id, **data)

def remove_schedule(request):
    job = jobs.get_owned(request.user.id, request.path_id)
    jobs.delete(job.id)
    return 204
```
migrations/004.sql lines 1-5 (added):
```sql
CREATE TABLE export_jobs (
 id INTEGER PRIMARY KEY,
 owner INTEGER NOT NULL,
 cron TEXT NOT NULL
);
```
deploy.yaml lines 12-14 (added):
```yaml
scheduler:
  command: python -m schedules.worker
  restart: always
```
The scheduler implementation is supplied as a verified component: validated schedules only; bounded queue; account-bound writes; durable idempotency; worker uses reports.build_csv; deletion is owner-checked. Removing scheduling would fail the approved scheduled-export acceptance. Existing PDF regression and CSV acceptance passed against head.
