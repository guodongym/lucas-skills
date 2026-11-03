# Repository snapshot

Complete offline artifacts for example/admin PR #302 "feat(forum): 接入论坛社群日报与运行记录". Base 3333333333333333333333333333333333333333; head 5555555555555555555555555555555555555555. No WIP. Locations use target-file coordinates. Supplied checks and walkthrough records are author-run, not reviewer-run. The application cannot be started in this offline scenario.

## Requirement and baseline

Approved owner spec F-8: operators connect a forum bot, collect channel messages, read generated daily reports and inspect collection runs in the admin UI.

- F-8 §6.2: pausing a channel during a run and enabling it again continues collection from the saved progress.
- F-8 §8.1: run detail shows channel, collection type, status, time range and failure reason; the daily report body is shown as a formatted document.
- F-8 §8.2 acceptance: settings → run records → run detail → daily report → back is usable in the admin UI.

Pre-change repository rules, unchanged by this PR:

- AGENTS.md:40: "新增或改造页面必须复用 `src/components` 的共用组件：结果工具栏与操作组使用 `ListToolbar`/`RowActions`，详情元数据使用 `Descriptions`，状态使用 `StatusTag` 并显示中文标签。确需自定义须在 PR 中说明原因；不得新增平行的布局写法。"
- docs/standards/interaction.md:140: "加载中保留页面结构并显示加载占位；数据返回前不得显示空状态文案。"
- docs/standards/interaction.md:150: "枚举值、ISO 时间和内部错误对象不直接展示给用户；时间统一显示北京时间。"
- docs/development-workflow.md:60: "新增页面合并前须提供可运行页面的人工走查记录：主任务路径，1440 与 1280 两种宽度，加载、空、错误和成功状态截图。测试通过不能替代走查。"

Closest existing feature (unchanged): `chat-group/ChatGroupRuns.tsx:1-6` imports `ListToolbar`, `RowActions`, `Descriptions`, `StatusTag` and `TableText` from `../../components`.

Shared code (unchanged): `components/MarkdownDocument.tsx:10` renders headings, lists and paragraphs from Markdown and is already used by the knowledge-base reader. `hooks/useResource.ts:8` returns `{ data: undefined, loading: true }` until the response arrives. `app/time.ts:5` `formatBeijing(iso)` formats timestamps in Asia/Shanghai.

## Head diff — backend

`server/forum/runs.py:52`:
```diff
+    if not channel.enabled:
+        return pause_run(run, reason="channel_disabled")
```
`server/forum/automation.py:44`:
```diff
+def resumable_runs():
+    return [run for run in paused_runs() if channel_enabled(run.channel_id)]
```
The scheduler resumes `resumable_runs()` from `run.cursor`. `tests/test_forum_runs.py:30` pauses a channel mid-run, re-enables it and asserts the run continues from the stored cursor without re-collecting earlier messages.

`server/forum/daily_report.py:25` returns Markdown with `##`/`###` headings as `body`.

## Head diff — frontend (new files)

`frontend/src/modules/forum/ForumSettings.tsx`:
```tsx
20 const connections = useResource(listConnections);
26 if (connections.loading) return <ContentCard title="接入设置"><Skeleton rows={4} /></ContentCard>;
27 if (!connections.data?.length) return <EmptyState description="尚未配置机器人连接" />;
```

`frontend/src/modules/forum/ForumRunDetail.tsx`:
```tsx
55 <ContentCard title="运行详情">
56   <Descriptions items={[
57     { label: '频道', content: run.channel_name },
58     { label: '采集类型', content: KIND_LABELS[run.kind] },
59     { label: '状态', content: <StatusTag theme={STATUS_THEMES[run.status]}>{STATUS_LABELS[run.status]}</StatusTag> },
60     { label: '时间范围', content: `${formatBeijing(run.range_start)} – ${formatBeijing(run.range_end)}` },
61     ...(run.status === 'failed' ? [{ label: '失败原因', content: run.error_message }] : []),
62   ]} />
63 </ContentCard>
```

`frontend/src/modules/forum/ForumRecords.tsx`:
```tsx
70 <ListToolbar actions={<RowActions placement="section">
71   <Button onClick={extract}>提取反馈</Button>
72   <Button onClick={backfill}>历史补采</Button>
73   <Button theme="danger" onClick={stop}>停止处理</Button>
74 </RowActions>} />
```

`frontend/src/modules/forum/ForumReport.tsx:38`: `<MarkdownDocument source={report.body} />`.

## Author PR note and walkthrough

"复用 PageHeader、ContentCard、FilterBar、ListPagination、ListToolbar、RowActions、Descriptions、StatusTag 与 MarkdownDocument，没有新增布局类。验证：typecheck 通过；Python 284/284；浏览器 18/18。"

Walkthrough record `docs/acceptance/forum-f8.md` (added in this PR): started the production build against a temporary database seeded with synthetic forum data; walked settings → run records → run detail → daily report → back at 1440 and 1280; screenshots for loading, empty, error and success states of each page are attached and listed by file name. Recorded observations: report headings render as headings, statuses show Chinese labels, action group stays left-aligned, failure reason appears only for failed runs. It states that the owner's visual confirmation is still pending and real forum/model access was not tested.

No dependency, schema or permission change.
