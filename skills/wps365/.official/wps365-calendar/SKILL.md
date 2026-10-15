---
name: wps365-calendar
description: "WPS 365 日历：管理日历、日程、参与者与忙闲查询。当用户需要查看日程安排、创建/修改/删除日程、查询忙闲时触发。"
metadata:
  requires:
    bins: ["wps365-cli"]
---

# 日历 (calendar)

> **前置条件：** 先阅读 `../wps365-shared/SKILL.md` 了解认证、全局参数和安全规则。

## 授权模型

日历所有操作均支持**用户授权（delegated）**：

```bash
wps365-cli auth login --scopes "kso.calendar.read,kso.calendar.readwrite,kso.calendar_events.read,kso.calendar_events.readwrite,kso.user_base.read"
```

## 快捷命令

| 命令 | 说明 |
|------|------|
| [`+insert`](../wps365-calendar-insert/SKILL.md) | 快速创建日程并管理参与者 |

## OAuth Scope

| Scope | 权限 | 用途 |
|-------|------|------|
| `kso.calendar.read` | 查询日历 | `calendar list`, `calendar get` |
| `kso.calendar.readwrite` | 管理日历 | `calendar create/update/delete` |
| `kso.calendar_events.read` | 查询日程 | `calendar event list`, `calendar free-busy` |
| `kso.calendar_events.readwrite` | 管理日程 | `calendar event create/update/delete` |
| `kso.user_base.read` | 查询当前用户 | 忙闲查询等场景需要 |

> **常见陷阱：**
> - 只申请 `kso.calendar.readwrite` 而漏了 `kso.calendar_events.readwrite`，写日程时返回 `400000003`
> - 查忙闲需要 `kso.calendar_events.read` + `kso.user_base.read`

## 日历操作

```bash
wps365-cli calendar --help
```

- `calendar list` — 列出所有日历
- `calendar primary batch-get` — 批量获取主日历
- `calendar get` — 获取指定日历
- `calendar create` / `calendar update` / `calendar delete`
- `calendar subscribe` / `calendar unsubscribe` — 订阅/取消订阅日历

## 日程操作

- `calendar event list` — 列出日程（支持增量同步）
- `calendar event-instance list` — 列出日程实例（展开重复日程，**推荐查看实际安排**）
- `calendar event-instance get` — 获取日程实例
- `calendar event get` — 获取日程详情
- `calendar event create` — 创建日程（详见 [calendar-insert](../wps365-calendar-insert/SKILL.md)）
- `calendar event update` — 修改日程
- `calendar event delete` — 删除日程
- `calendar event search` — 搜索日程
- `calendar event respond` — 答复日程邀请
- `calendar event-minutes create` — 创建会议纪要

## 参与者管理

- `calendar event-attendee list` — 查看参与者列表
- `calendar event-attendee add` — 添加参与者
- `calendar event-attendee remove` — 删除参与者

## 会议室关联

- `calendar event-room list` — 查看日程关联的会议室
- `calendar event-room add` — 为日程添加会议室
- `calendar event-room remove` — 移除会议室

## 忙闲查询

```bash
wps365-cli calendar free-busy \
  --start-time "2026-04-01T00:00:00+08:00" \
  --end-time "2026-04-01T23:59:59+08:00" \
  --user-ids "nVyy56L"
```

> 时间区间最大 **7 天**；最多 **50** 个用户或 **50** 个会议室。

## 常见用法

```bash
# 查询日历列表
wps365-cli calendar list

# 查看今天的日程
wps365-cli calendar event-instance list primary \
  --start-time "2026-04-01T00:00:00+08:00" \
  --end-time "2026-04-01T23:59:59+08:00"

# 搜索日程
wps365-cli calendar event search primary \
  --keyword "周例会" \
  --start-time "2026-04-01T00:00:00+08:00" \
  --end-time "2026-04-07T23:59:59+08:00"

# 创建日程（详见 calendar-insert skill）
wps365-cli calendar event create primary \
  --name "产品评审" \
  --from "2026-04-01T14:00:00+08:00" \
  --to "2026-04-01T15:00:00+08:00"
```

## 限制

- 日程查询时间区间最大 **31 天**
- 忙闲查询时间区间最大 **7 天**
- 每天最多创建 **500** 个日程
- 最多 **100** 个日历
- 分页每页最大 **20** 条

## 另请参阅

- [wps365-shared](../wps365-shared/SKILL.md) — 全局参数、认证与调试
- [wps365-calendar-insert](../wps365-calendar-insert/SKILL.md) — 快速创建日程
- [wps365-user](../wps365-user/SKILL.md) — 搜索用户获取 open_id
