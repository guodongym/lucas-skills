---
name: wps365-calendar-insert
description: "WPS 365 日历：快速创建日程、关联在线会议并管理参与者。当用户要预约会议、创建日程邀请同事时触发。"
metadata:
  requires:
    bins: ["wps365-cli"]
---

# 创建日程 (calendar event create)

> **前置条件：** 先阅读 `../wps365-shared/SKILL.md` 了解认证、全局参数和安全规则。

快速创建日程，可选地附加在线会议并添加参与者。

## 必要 Scope

```bash
wps365-cli auth login --scopes "kso.calendar.read,kso.calendar.readwrite,kso.calendar_events.read,kso.calendar_events.readwrite,kso.user_base.read,kso.contact.read"
```

## 用法

```bash
wps365-cli calendar event create <calendar-id> \
  --name "<标题>" \
  --from "<RFC3339 开始时间>" \
  --to "<RFC3339 结束时间>" \
  [--description "<描述>"] \
  [--location "<地点>"] \
  [--reminders "15,5"] \
  [--online-meeting-body '<JSON>']
```

## 参数

| 参数 | 必填 | 说明 |
|------|------|------|
| `<calendar-id>` | 是 | 日历 ID（位置参数），主日历可用 `primary` |
| `--name` | — | 日程标题 |
| `--from` | 是 | 开始时间，RFC3339 格式（必须带时区） |
| `--to` | 是 | 结束时间，RFC3339 格式（必须带时区） |
| `--description` | — | 日程描述，最长 2000 字符 |
| `--location` | — | 地点名称 |
| `--reminders` | — | 提醒时间（分钟），多个用逗号分隔，如 `"30,10"` |
| `--online-meeting-body` | — | 在线会议配置 JSON |

### 时间格式

**必须带时区**，推荐 `+08:00`（北京时间）：

```
2026-04-01T10:00:00+08:00
```

### 在线会议配置

通过 `--online-meeting-body` 附加在线会议（`provider` 为 `kso` 或 `third_party`）：

```bash
--online-meeting-body '{"provider":"kso"}'
```

## 示例

### 基本日程

```bash
wps365-cli calendar event create primary \
  --name "项目评审" \
  --from "2026-04-01T14:00:00+08:00" \
  --to "2026-04-01T15:00:00+08:00"
```

### 带在线会议的日程

```bash
wps365-cli calendar event create primary \
  --name "产品讨论会" \
  --from "2026-04-01T10:00:00+08:00" \
  --to "2026-04-01T11:00:00+08:00" \
  --description "讨论 Q2 产品规划" \
  --reminders "15" \
  --online-meeting-body '{"provider":"kso"}'
```

### 带地点和提醒的日程

```bash
wps365-cli calendar event create primary \
  --name "团队周会" \
  --from "2026-04-01T10:00:00+08:00" \
  --to "2026-04-01T11:00:00+08:00" \
  --location "3F 会议室" \
  --reminders "30,10"
```

## 完整流程：创建日程 + 添加参与者

### 第一步：搜索用户获取 open_id

```bash
wps365-cli user search --keyword "孟文韬" --page-size 20 --status active --search-field user_name
# → data.items[].id 即为 open_id
```

### 第二步：创建日程

```bash
wps365-cli calendar event create primary \
  --name "技术方案讨论" \
  --from "2026-04-01T10:00:00+08:00" \
  --to "2026-04-01T11:00:00+08:00" \
  --online-meeting-body '{"provider":"kso"}'
# → 返回 data.id 为新日程 event_id
```

### 第三步：添加参与者

```bash
wps365-cli calendar event-attendee add primary "<event_id>" \
  --user-ids "<open_id_1>,<open_id_2>"
```

**参数说明：**

| 参数 | 必填 | 说明 |
|------|------|------|
| `<calendar-id>` | 是 | 日历 ID（位置参数），主日历可用 `primary` |
| `<event-id>` | 是 | 日程 ID（位置参数，创建时返回） |
| `--user-ids` | 条件 | 用户 open_id，多个用逗号分隔 |
| `--attendees-body` | 条件 | 高级参数，完整 JSON（支持 user、group、third_party_email） |
| `--no-notification` | — | 不发送通知 |

### 高级：添加第三方邮箱参与者

```bash
wps365-cli calendar event-attendee add primary "<event_id>" \
  --attendees-body '[{"type":"third_party_email","third_party_email":"guest@example.com"}]'
```

### 查看参与者

```bash
wps365-cli calendar event-attendee list primary "<event_id>" \
  --page-size 20
```

### 删除参与者

```bash
wps365-cli calendar event-attendee remove primary "<event_id>" \
  --user-ids "<open_id>"
```

> [!IMPORTANT]
> `calendar event update` 接口**不支持**通过 attendees 字段修改参与者，必须使用独立的 `event-attendee add` / `event-attendee remove` 命令。

## 提示

- 使用 `--dry-run` 预览请求，确认无误再执行。
- 创建后从返回 JSON 中取 `data.id` 字段用于后续操作。
- 主日历的 `calendar_id` 可直接使用 `primary`。

> [!CAUTION]
> 创建日程是**写操作** — 执行前请先与用户确认。

## 另请参阅

- [wps365-shared](../wps365-shared/SKILL.md) — 全局参数、认证
- [wps365-calendar](../wps365-calendar/SKILL.md) — 所有日历与日程操作
- [wps365-user](../wps365-user/SKILL.md) — 搜索用户获取 open_id
- [wps365-drive](../wps365-drive/SKILL.md) — 创建会议文档
