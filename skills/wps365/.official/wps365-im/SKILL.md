---
name: wps365-im
description: "WPS 365 即时通讯：发送消息（用户授权走 POST /v7/messages/create；多用户则循环；batch_create 仅应用身份）、管理会话与群聊；支持用用户授权查看消息会话列表（im chats list）。当用户需要发消息、创建群聊、查看会话列表或未读时触发。"
metadata:
  requires:
    bins: ["wps365-cli"]
---

# 即时通讯 (im)

> **前置条件：** 先阅读 `../wps365-shared/SKILL.md` 了解认证、全局参数和安全规则。
>
> **存量升级客户（Agent 必做）：** 若发消息相关命令行为异常，先按 `wps365-shared` 用 skills 包内 `spec/` **覆盖**本机 `api.yaml`/`curated.yaml`。用户授权发消息统一走 **`/v7/messages/create`**（见下文），不要依赖 `batch_create` 的 delegated。

## 授权模型

> [!IMPORTANT]
> CLI 会根据操作的 OpenAPI `security` **自动选择** token；可用 `--token-type delegated|app` 显式覆盖。

| 授权类型 | 操作范围 | 所需 Scope |
|---------|---------|-----------|
| **delegated（用户授权）** | **发消息（create，单收件人；多用户则循环）**、查看会话列表、查询未读、读历史消息 | `kso.chat.read` / `kso.chat_message.readwrite`（按操作） |
| **app** | 会话管理、群管理、**批量发消息 `batch_create` / 部门广播** | `kso.chat.readwrite`, `kso.chat_message.readwrite` |

### 登录示例

```bash
# delegated — 发消息用 create / 查「我的」会话 / 未读
wps365-cli auth login --device --scopes "kso.chat.read,kso.chat_message.readwrite"

# app — 批量 batch_create / 部门等（须显式 --token-type app）
export WPS365_CLIENT_ID="<client-id>"
export WPS365_CLIENT_SECRET="<client-secret>"
wps365-cli im message send --to "u1,u2" --text "hello" --token-type app
```

## 核心用法

### 获取会话列表（用户授权的消息会话）

`im chats list` 返回**当前身份可见/已授权**的消息会话列表（GET `/v7/chats`），支持分页。  
用 **delegated** 时即当前登录用户的会话列表；也可用 app（视应用权限与数据范围而定）。

```bash
# 用户授权身份查看会话列表（推荐）
wps365-cli im chats list --page-size 20 --token-type delegated

# 下一页：传入上一页响应中的 next_page_token
wps365-cli im chats list --page-size 20 --page-token "<next_page_token>" --token-type delegated
```

| 参数 | 说明 |
|------|------|
| `--page-size` | 每页数量，1–100 |
| `--page-token` | 分页标记（取响应 `next_page_token` / `data.next_page_token`） |
| `--token-type` | `delegated`（用户会话）或 `app` |

> 运行时子命令名为 **`im chats`**（复数）。若写 `im chat list` 会找不到命令，请用 `im chats list`。

### 查看会话 / 群聊历史消息（从最近开始）

`im chat-message list` 拉取某会话的历史消息。不传 `--order` 时网关/默认多为 **asc（从最早开始）**，在长群聊里会极慢且难用。

**Agent 默认必须加 `--order desc`**（新 → 旧）；只有用户明确要求「从最早翻」时才用 `asc`。

```bash
# 推荐：从最近消息开始查
wps365-cli im chat-message list "<CHAT_ID>" --page-size 20 --order desc

# 下一页（仍保持 desc）：传入上一页的 next_page_token
wps365-cli im chat-message list "<CHAT_ID>" \
  --page-size 20 --order desc --page-token "<next_page_token>"

# 可选：限定时间窗（毫秒时间戳），进一步缩小范围
wps365-cli im chat-message list "<CHAT_ID>" \
  --page-size 50 --order desc --start <START_MS> --end <END_MS>
```

| 参数 | 说明 |
|------|------|
| `--order` | **`desc`（推荐，最近优先）** / `asc`（最早优先） |
| `--page-size` | 每页数量，1–100 |
| `--page-token` | 分页标记（取响应 `next_page_token`） |
| `--start` / `--end` | 起止时间戳（毫秒），按需过滤 |

> 这是**某个 chat 的消息记录**，不是会话列表。会话列表用上面的 `im chats list`。

### 发送文本消息

> **关键约束：** `POST /v7/messages/batch_create`（精装 `im message send`）**实际仍以应用身份为主，不支持可靠的用户授权批量发送**。凡需要 **delegated（用户授权）** 发消息，一律走 `POST /v7/messages/create`（单数 `receiver`）；要对多个 user 发同一内容时，**按人循环、多次 create**，不要用 `--to "u1,u2"` 指望一次 batch。

#### 请求结构体（`/v7/messages/create`，用户授权）

单次请求只对应**一个**接收者：

```json
{
  "type": "text",
  "receiver": {
    "receiver_id": "<ID>",
    "type": "user"
  },
  "content": {
    "text": {
      "content": "test",
      "type": "plain"
    }
  }
}
```

| 字段 | 说明 |
|------|------|
| `type` | `"text"` |
| `content.text.type` | `"plain"` 或 `"markdown"` |
| `content.text.content` | 文本正文 |
| `receiver.type` | `"user"`（私聊用户）或 `"chat"`（群聊） |
| `receiver.receiver_id` | 用户 open_id，或群聊 chat_id |

成功响应关键字段：`data.message_id`、`data.chat_id`、`data.ctime`。

#### 向单个用户发送（delegated）

```bash
wps365-cli api post /v7/messages/create --data '{
  "type": "text",
  "receiver": {
    "type": "user",
    "receiver_id": "<OPEN_ID>"
  },
  "content": {
    "text": {
      "type": "plain",
      "content": "test"
    }
  }
}'
```

#### 向多个用户发送（delegated：循环多次 create）

对每个 open_id **各发一次** `messages/create`（body 仅改 `receiver.receiver_id`）。Agent 须串行或可控并发完成全部目标用户，并分别核对每次 `code==0` / `message_id`；**禁止**为此改用 `im message send --to "u1,u2"`（那是 batch，走不了用户授权）。

```bash
# 示例：给 u1、u2 各发一条（同一正文，两次请求）
for uid in u1 u2; do
  wps365-cli api post /v7/messages/create --data "{
    \"type\": \"text\",
    \"receiver\": {\"type\": \"user\", \"receiver_id\": \"${uid}\"},
    \"content\": {\"text\": {\"type\": \"plain\", \"content\": \"test\"}}
  }"
done
```

#### 向群聊发送（delegated：`receiver.type=chat`）

```bash
wps365-cli api post /v7/messages/create --data '{
  "type": "text",
  "receiver": {
    "type": "chat",
    "receiver_id": "<CHAT_ID>"
  },
  "content": {
    "text": {
      "type": "plain",
      "content": "test"
    }
  }
}'
```

> **不要**把 ID 塞进 `receivers[].receiver_ids` 再调 create；create 只有 `receiver.receiver_id`。

#### 应用身份批量 / 部门等（精装 `im message send` → `batch_create`）

仅在明确需要 **app** 身份、或部门/公司等 batch 能力时使用精装命令（须配置应用凭证，并加 `--token-type app`）：

```bash
wps365-cli im message send --to "u1,u2" --text "通知内容" --token-type app
wps365-cli im message send --receiver-type dept --to "dept_1" --text "部门通知" --token-type app
wps365-cli im message send --to "<OPEN_ID>" --text "**重要通知**" --text-format markdown --token-type app
```

**精装参数说明：**

| 参数 | 必填 | 说明 |
|------|------|------|
| `--to` | 是 | 接收者 ID，多个用逗号分隔（仅 batch/app 场景） |
| `--text` | 是 | 发送的文本内容 |
| `--receiver-type` | — | `user`（默认）、`dept`、`company`、`chat` 等 |
| `--text-format` | — | `plain`（默认）、`markdown` |

### 查看未读消息数

```bash
# delegated
wps365-cli im unread-chat count --token-type delegated
```

### 创建群聊

```bash
wps365-cli im chats create \
  --type group \
  --member-ids "nVyy56L,QzwLaPR" \
  --name "项目群" \
  --owner-id "nVyy56L"
```

### 获取 P2P 会话

```bash
wps365-cli im p2p-chat get --user-id "<OPEN_ID>"
```

### 更新群信息 / 解散群

```bash
wps365-cli im chats update "<CHAT_ID>" --name "新群名"
wps365-cli im chats delete "<CHAT_ID>"
```

### 移除群成员

```bash
wps365-cli im chat-member remove "<CHAT_ID>" --user-ids "u1,u2"
```

## 更多操作

```bash
wps365-cli im --help
wps365-cli im chats --help
wps365-cli im messages --help
```

### 消息

- **用户授权发消息（推荐）** — `api post /v7/messages/create`（`receiver.type=user|chat`）；多用户则**循环多次** create
- `im messages send` — **应用身份**批量发文本（`batch_create`；多人/部门等）
- `im messages recall` — 撤回消息
- `im chat-message list` — 查看会话历史消息（**默认加 `--order desc`**，从最近往前翻）
- `im chat-message get` — 获取指定消息
- `im chat-message reply` — 回复消息

### 会话管理

- `im chats list` — **用户授权的消息会话列表**（delegated / app）
- `im chats get` / `im p2p-chat get`
- `im chats create` / `im chats update` / `im chats delete`
- `im unread-chat count` — 未读消息数（delegated）

### 群成员管理

- `im chat-member list` — 群成员列表
- `im chat-member add` — 添加群成员
- `im chat-member remove` — 移除群成员

## 常见陷阱

| 问题 | 原因 | 解决 |
|------|------|------|
| `unknown command "chat"` | 子命令是 `chats`（复数） | 使用 `im chats list` 等 |
| 查群消息极慢 / 总是很旧的内容 | 未加 `--order`，按 **asc 从最早** 翻 | **加 `--order desc`**；可用 `--start`/`--end` 限时间窗 |
| 发消息走了 app / `delegated is incompatible` | `batch_create` **不支持**可靠的用户授权批量发送；或本机旧 spec | **delegated 一律用 `messages/create`**；多用户则循环；仅 app 批量时用精装 + `--token-type app`；必要时覆盖 skills 包 `spec/` |
| 想一次 `--to u1,u2` 用用户身份群发 | batch 无用户授权 | 对每个 user **多次** `api post /v7/messages/create`，`receiver.type=user` |
| 向群聊发失败 / body 字段对不上 | 误用 `receivers[].receiver_ids` | create body：`receiver: {type:"chat"|"user", receiver_id:"..."}` + `content.text` |
| 会话列表为空 / 权限错误 | 未用 delegated，或缺少 `kso.chat.read` | `auth login --scopes "kso.chat.read"` 后加 `--token-type delegated` |
| `No App token found` | 未配置应用凭证却走了 batch/app | 配置 `WPS365_CLIENT_ID` / `SECRET`，或改用 delegated + `messages/create` |
| `InvalidMessage` | 消息体格式不正确 | 按上文 create 结构体重试 |
| `invalid user_id` | 用了 account_id 而非 open_id | 通过 `user search` 获取 open_id |

> [!CAUTION]
> 发送消息、管理群成员是**写操作** — 执行前请先与用户确认。

## 另请参阅

- [wps365-shared](../wps365-shared/SKILL.md) — 全局参数与认证
- [wps365-user](../wps365-user/SKILL.md) — 搜索用户获取 open_id
