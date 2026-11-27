# Repository snapshot

Complete offline artifacts for example/studio PR #880 "feat(tasks): 任务进度与成果提交". Base bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb; head cccccccccccccccccccccccccccccccccccccccc. No WIP. Locations use target-file coordinates. Supplied checks are author-run, not reviewer-run. The application cannot be started in this offline scenario.

## Sources that exist before this PR (unchanged)

- Owner issue #870: "任务列表里看不出谁在做、做完没有。需要在列表显示任务进度，做完能看到成果。"
- `docs/decisions.md:12` (owner-approved 2026-11-01): "项目内业务协作默认向所有正式成员开放；业务上的负责人、执行人指派不改变权限。某个动作需要收紧时，由模块需求写明理由并经产品确认。"
- `docs/workflow.md:8`: "新的业务行为先由产品确认需求，再进入开发。"
- Existing product behavior: in the editor, a task's **开始制作** button creates its workspace; **提交成果** in the editor publishes the selected result to the task. The task list currently shows title, assignee and due date only; tasks have no status field.

## Documents added by this PR

`docs/requirements/task-progress.md` (new; no product sign-off recorded) defines:

- Roles: 执行人, 需求跟进人, 管理员. Only the assignee may record start, add notes or submit; plan edits are limited to the assignee, the requirement follower or an admin.
- Terms shown in the UI: 登记开工, 补充说明, 免审交稿, 本轮交稿.
- Each task may have up to 100 custom stages; changing a date requires a reason.

`requirements.follower_user_id` already exists as an optional field for who follows a requirement; it is not used by any permission check before this PR.

## Head changes (52 files, +3,980 / -110)

| Area | Change |
| --- | --- |
| `migrations/0090_task_progress.sql` | new tables `task_progress` (plan, stages JSON up to 100, `started_at`, `progress_revision`) and `task_progress_commands` (append-only log of every action with payload hash, unique `(user_id, request_id)`, generated column + unique index allowing one `submit` per task) |
| `backend/tasks/progress_status.sql.go` | task status computed on every read: has `submit` command → completed; else `started_at` → in progress; else not started |
| `backend/tasks/progress_service.go` | actions `plan`, `start`, `note`, `submit`; every action, including `note`, requires both `expectedTaskRevision` and `expectedProgressRevision` and fails with 409 on mismatch |
| `backend/tasks/progress_permissions.go` | implements the role rules from the new requirements doc, using `follower_user_id` as a permission role |
| `backend/shared/permission_service.go`, `backend/shared/workspace_service.go` | adds a `StrictRoleLookup` flag to the shared permission service and injects the permission service into the shared workspace service so that a role-lookup error can be told apart from a denial; the only caller that sets the flag is the new progress service |
| `frontend/src/tasks/TaskProgressDialog.vue` | new "进度与交付" dialog opened from the task list, with buttons 登记开工 (stores the server time), 补充说明, and 免审交稿 (search project assets and pick an archived image version) |
| `frontend/src/tasks/taskProgress.ts` | persists a pending request in `sessionStorage` and replays it after network errors |
| tests | +1,620 |

The editor's 开始制作 and 提交成果 buttons are unchanged and do not write `task_progress`.

## Author checks

Backend unit 214/214, frontend unit 96/96, lint passed.
