---
name: wps365-mcp
description: "WorkBuddy / Claude / Cursor 通过本地 MCP 接入 WPS 365（企业账号）。当用户要配 WPS365 连接器、mcp.json、mcp serve，或把企业 365 与金山文档个人连接器（mcp-center.wps.cn / kdocs）搞混时使用。授权：config init 建应用，再 auth login。不负责个人金山文档 MCP。"
metadata:
  requires:
    bins: ["wps365-cli"]
---

# WPS 365 MCP（WorkBuddy）

把本机 `wps365-cli` 暴露为 stdio MCP server，供 WorkBuddy 自定义连接器、Claude、Cursor 调用精装命令。凭证与 CLI 相同，**不走** `https://mcp-center.wps.cn/skill_hub/mcp`。

> **前置：** 认证细节见 `../wps365-shared/SKILL.md`；从零安装见 `../wps365-getting-started/SKILL.md`。业务操作仍走各域 skill（drive / calendar / …），本 skill 只负责 **MCP 接入与授权**。

## 与金山文档连接器的区别

| | 金山文档 `kdocs` 连接器 | 本 MCP（WPS 365） |
|--|------------------------|-------------------|
| 配置 | 远端 URL `mcp-center.wps.cn` | 本机 `wps365-cli mcp serve` |
| 账号 | 个人金山文档 | **企业** WPS 365 |
| 授权 | 个人 Token | `config init` + `auth login --device` |

用户说「WorkBuddy 里连金山文档、企业账号用不了」→ 不要去改 kdocs；按本 skill 接 365。个人文档继续用 kdocs。

## Agent 执行顺序

1. `wps365-cli version` — 没有则先装（getting-started 步骤 1）。需要带 `mcp serve` 的版本（本仓库 `mcp` 子命令）。
2. `wps365-cli auth status` — 已有 delegated 且 `user me` 能通则跳到第 5 步。
3. **建应用**：后台跑下面命令，从输出取出浏览器链接原样发给用户（不要改 URL），等命令自己退出。

```bash
wps365-cli config init --new
```

4. **用户授权**：必须 `--device`，必须带本次要用的 `--scopes`。启动后把验证链接给用户，**保持进程存活**直到成功。

```bash
wps365-cli auth login --device --scopes "kso.user_base.read"
wps365-cli user me
```

按业务追加 scope（日历 `kso.calendar.read`，云文档 `kso.drive.readwrite` 等），以域 skill / `--help` 为准。未开通的 scope 会 `invalid_scope`。

5. **写入 MCP 配置**：把本 skill 目录（或仓库 `connectors/workbuddy/mcp.json`）里的 `mcp.json` 合并进客户端配置，或生成一份：

```bash
wps365-cli mcp config --app workbuddy
```

WorkBuddy：自定义连接器 / `~/.workbuddy/mcp.json`。Claude / Cursor：`--app claude` 或 `--app cursor`。`command` 不在 PATH 时改成 `wps365-cli` 的绝对路径。

规范内容：

```json
{
  "mcpServers": {
    "wps365": {
      "timeout": 600,
      "command": "wps365-cli",
      "args": ["mcp", "serve"],
      "env": {}
    }
  }
}
```

6. 客户端信任/重启 MCP 后，用 `wps365-cli mcp doctor` 检查 spec 与凭证。CLI 暴露的 tool 名形如 `calendar_event_create`（catalog id 的 `.`/`-` 换成 `_`，**不加** `wps365_`）。WorkBuddy 会用 server 名 `wps365` 拼出 `wps365_calendar_event_create` / `mcp__wps365__calendar_event_create`。需要过滤域时：`wps365-cli mcp serve --domains calendar,im`（WorkBuddy 对启用工具 >80 会警告影响回复质量，可用 `--domains` 收窄）。

Windows 上的 WorkBuddy 必须指向 `wps365-cli.exe` 的绝对路径；它**不会**读 WSL 的 `~/.config/wps365-cli`，需要在 Windows 再做一次 `config init` / `auth login --device`。

## 禁止

- 不要让企业用户去连 WorkBuddy 官方「金山文档」连接器当 365 用。
- 不要把 MCP 配成 `mcp-center.wps.cn`。
- 不要用不带 `--device` 的 `auth login`（会占本地回调端口）。
- 不要在展示授权 URL 后立刻杀掉 `config init` / `auth login --device`。
- 不要因为 MCP 报 `not_found` / 缺 `client_id` 去跑 `auth setup`。先 `config init --new`，再 `auth login --device --scopes "..."`。`auth setup` 只用于用户手里已经有 AK/SK。
- 需要 PNG 二维码时：`wps365-cli auth qrcode --file qr.png "<验证 URL>"`（不要用全局 `--output` 当路径）。
- 不要向用户复述 `client_secret` / access token。

## 失败对照

| 现象 | 处理 |
|------|------|
| `mcp serve` 不是命令 | CLI 太旧，先升级到带 MCP 的版本 |
| `not_found` / 缺 `client_id` | 先 `wps365-cli config init --new`，完成后再 `auth login --device --scopes "..."`；不要 `auth setup` |
| tools/call 认证失败 | `auth status`；无应用则回到上一步 `config init --new` |
| `invalid_scope` | 应用后台开通对应权限后，带齐 `--scopes` 再 `auth login --device`。airpage 常见：`kso.airpage.readwrite,kso.drive.readwrite,kso.file.readwrite` |
| `403000001` / `interface_company_doc` | 企业套餐权益，不是 OAuth scope；见 shared skill |
| 个人账号进不了开放平台 | 365 只对企业账号；个人文档走 kdocs 连接器 |
| WorkBuddy 工具名仍是 `wps365_wps365_*` | CLI 太旧；升级到去掉 `wps365_` 前缀的版本并重载 MCP |
| WorkBuddy「启用工具数量过多」 | `args` 里给 `mcp serve --domains drive,airpage` 等，或在 UI 关掉不用的域 |

业务读写文档/日历/消息：完成本 skill 第 1–5 步后，转到对应域 skill，不要在本文件展开命令清单。
