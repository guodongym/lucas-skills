---
name: wps365-mail-core
description: "WPS 365 邮件核心能力：邮箱列表、目录浏览、邮件查询/草稿/发送/搜索。当用户需要收发邮件、查看目录、按条件检索邮件时触发。"
metadata:
  requires:
    bins: ["wps365-cli"]
---

# 邮件核心 (mail core)

> **前置条件：** 先阅读 `../wps365-shared/SKILL.md` 了解认证、全局参数和安全规则。

## 授权模型

- `mail message search` 描述为"仅支持用户登录后访问自己的邮箱"，建议优先使用 delegated。
- 其余命令按接口 security 由 CLI 自动选择；如遇权限冲突，优先查看 `auth status` 并按错误补 scope。

## 核心命令面

```bash
wps365-cli mail --help
```

### 邮箱

- `mail mailbox list` — 获取邮箱列表
- `mail mailbox-folder list` — 获取邮箱目录列表
- `mail mailbox-subfolder list` — 获取子目录列表

### 邮件

- `mail message list` — 获取邮件列表
- `mail message get` — 获取邮件详情
- `mail message search` — 高级搜索邮件

### 草稿

- `mail draft create` — 创建草稿
- `mail draft send` — 发送草稿

## 常用流程

### 流程 A：公共邮箱巡检

```bash
# 1) 列出邮箱
wps365-cli mail mailbox list --page-size 20

# 2) 查看目录
wps365-cli mail mailbox-folder list "mbx_xxx"

# 3) 查看子目录
wps365-cli mail mailbox-subfolder list --mailbox-id "mbx_xxx" --folder-id "inbox"
```

### 流程 B：草稿 -> 发信

```bash
# 1) 创建草稿
wps365-cli mail draft create --mailbox-id "mbx_xxx" \
  --subject "项目同步" \
  --body "本周进展见附件" \
  --to "a@example.com,b@example.com"

# 2) 发送草稿（message-id 使用上一步返回 data.message_id / data.id）
wps365-cli mail draft send --mailbox-id "mbx_xxx" --message-id "msg_xxx"
```

### 流程 C：按条件检索邮件

```bash
# 查询收件箱未读
wps365-cli mail message list --mailbox-id "mbx_xxx" --folder-id inbox \
  --page-size 10 \
  --filter unread

# 全局高级搜索（支持关键词、发件人、附件等）
wps365-cli mail message search \
  --mailbox-ids "mbx_xxx" \
  --keyword "项目报告" \
  --has-attachment true \
  --page-size 5
```

## 关键参数与约束

- `mail message list --folder-id` 支持系统目录标识：`inbox`、`drafts`、`sent`、`junk`、`trash`。
- `mail message list --page-size` 范围 `1-10`。
- `mail message get` 需要 `mailbox-id + folder-id + message-id` 三个维度都匹配。

## 常见排错

| 现象 | 常见原因 | 处理建议 |
|------|----------|----------|
| `--token-type=delegated is incompatible with operation security` | 当前操作不支持 delegated | 移除强制 token-type，让 CLI 自动选；或改用 `--token-type app` |
| 400 参数错误（收件人） | `--to/--cc/--bcc` 格式不合法 | 使用逗号分隔邮箱，不要混入空格和中文逗号 |
| 查不到邮件 | `mailbox-id` 与 `folder-id` 不匹配 | 先 `mailbox-folder list` 确认目录，再查询 |

## 安全提示

- `draft create`、`draft send` 属于写操作，执行前确认用户意图与影响范围。

## 另请参阅

- [wps365-shared](../wps365-shared/SKILL.md) — 全局参数、认证与调试
