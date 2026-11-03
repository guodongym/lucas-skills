# Repository snapshot

Complete offline artifacts for example/admin PR #301 "feat(forum): 接入论坛社群日报与运行记录". Base 3333333333333333333333333333333333333333; head 4444444444444444444444444444444444444444. No WIP. Locations use target-file coordinates. Supplied checks are author-run, not reviewer-run. The application cannot be started in this offline scenario.

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

Closest existing feature (unchanged): `chat-group/ChatGroupRuns.tsx:1-6` imports `ListToolbar`, `RowActions`, `Descriptions`, `StatusTag` and `TableText` from `../../components`; its run detail renders `<Descriptions>` items and `<StatusTag>{STATUS_LABELS[run.status]}</StatusTag>`.

Shared code (unchanged):

- `components/patterns.css:119`: `.admin-form-actions { display: flex; justify-content: space-between; }`. The components README describes it as a form footer with one secondary group on the left and the primary action on the right.
- `chat-group/DailyReportDocument.tsx:12`: splits the body on lines matching `/^【(.+)】$/` into titled sections; every other line is rendered verbatim as a paragraph.
- `hooks/useResource.ts:8`: returns `{ data: undefined, loading: true }` until the response arrives.

## Head diff — backend

`server/forum/runs.py:52`:
```diff
+    if not channel.enabled:
+        return fail_run(run, code="disabled", message="频道已暂停")
```
`server/forum/automation.py:44`:
```diff
+def retry_ready(run):
+    return run.status == "failed" and run.error_code in {"interrupted", "network", "upstream_5xx"}
```
The scheduler resumes a failed run only when `retry_ready` is true. Manual "重新发起" creates a new run starting at the channel's history start. No other path resumes a failed run.

`server/forum/daily_report.py:25`:
```diff
+def render_daily_report(summary):
+    return "\n".join(["## 今日概览", summary.overview, "### 热门话题", *summary.topics])
```
`GET /api/forum/reports/{id}` returns this string as `body`.

## Head diff — frontend (new files)

`frontend/src/modules/forum/ForumSettings.tsx`:
```tsx
20 const connections = useResource(listConnections);
26 if (!connections.data?.length) return <EmptyState description="尚未配置机器人连接" />;
27 return <ContentCard title="接入设置">{/* connection table */}</ContentCard>;
```

`frontend/src/modules/forum/ForumRunDetail.tsx`:
```tsx
55 <ContentCard title="运行详情">
56   <p>状态：{run.status}</p>
57   <p>范围：{run.range_start} – {run.range_end}</p>
58   {run.error && <Alert theme="error" message={JSON.stringify(run.error)} />}
59 </ContentCard>
```
Example API response for a successful run: `{"status":"completed","kind":"incremental","channel_id":"9","range_start":"2026-10-01T00:00:00Z","range_end":"2026-10-02T00:00:00Z","error":{}}`.

`frontend/src/modules/forum/ForumRecords.tsx`:
```tsx
70 <div className="admin-form-actions">
71   <Button onClick={extract}>提取反馈</Button>
72   <Button onClick={backfill}>历史补采</Button>
73   <Button theme="danger" onClick={stop}>停止处理</Button>
74 </div>
```

`frontend/src/modules/forum/ForumReport.tsx`:
```tsx
3  import { DailyReportDocument } from '../chat-group/DailyReportDocument';
38 <DailyReportDocument body={report.body} />
```

## Author PR note

"复用了共用的 PageHeader、ContentCard、FilterBar、ListPagination 与群聊日报渲染。验证：typecheck 通过；Python 281/281；浏览器 16/16（检查接口调用与页面文字存在）。" No walkthrough record or screenshot is supplied. No dependency, schema or permission change.
