---
name: wps365-meeting
description: "WPS 365 会议：在线会议管理、参会人管理。当用户需要管理在线会议时触发。"
metadata:
  requires:
    bins: ["wps365-cli"]
---

# 会议 (meeting)

> **前置条件：** 先阅读 `../wps365-shared/SKILL.md` 了解认证、全局参数和安全规则。

## 授权模型

| 授权类型 | 操作范围 | 登录方式 |
|---------|---------|---------|
| **delegated / app** | 会议查询、结束、参会人管理 | `wps365-cli auth login` 或 `--app` |
| **delegated only** | 录制分享、开始/停止录制 | `wps365-cli auth login` |

### 登录示例

```bash
wps365-cli auth login --scopes "kso.meeting.read,kso.meeting.readwrite"
```

## OAuth Scope

| Scope | 权限 |
|-------|------|
| `kso.meeting.read` | 查询会议 |
| `kso.meeting.readwrite` | 管理会议 |

## 在线会议 vs 日程

WPS 365 的"在线会议"通常通过**日程**创建并关联：

```bash
wps365-cli calendar event create primary \
  --name "产品评审" \
  --from "2026-04-01T14:00:00+08:00" \
  --to "2026-04-01T15:00:00+08:00" \
  --online-meeting-body '{"provider":"kso"}'
```

详见 [wps365-calendar-insert](../wps365-calendar-insert/SKILL.md)。

`meeting` 域下的命令主要用于**管理已创建的在线会议**（查询、结束、参会人管理、纪要、录制）。

## 会议操作

```bash
wps365-cli meeting --help
```

### 会议

- `meeting list` — 获取会议列表
- `meeting get` — 获取会议详情
- `meeting end` — 结束会议

### 参会人

- `meeting participant list` — 参会人列表
- `meeting participant invite` — 邀请参会人
- `meeting participant remove` — 移除参会人
- `meeting set-host` — 设置主持人

### 会议纪要

- `meeting minute list` — 获取纪要列表
- `meeting minute-summary get` — 获取总结要点
- `meeting minute-transcript get` — 获取语音转写

### 录制

- `meeting recording list` — 获取录制列表
- `meeting recording-summary get` — 获取录制总结要点
- `meeting recording-transcript get` — 获取录制语音转写

> [!CAUTION]
> 创建/结束会议是**写操作** — 执行前请先与用户确认。

## 另请参阅

- [wps365-shared](../wps365-shared/SKILL.md) — 全局参数与认证
- [wps365-calendar-insert](../wps365-calendar-insert/SKILL.md) — 通过日程创建在线会议
