---
name: wps365-shared
description: "WPS365 CLI 共享基础：安装验证、OAuth2 认证配置（auth setup/login/refresh/status/logout）、delegated 与 app 身份选择、token 类型与 scope 规则、spec 文件管理（spec add/set/status/path）、环境变量（WPS365_CONFIG_DIR/WPS365_ACCESS_TOKEN/WPS365_KEYRING_BACKEND）、全局输出格式（--output）、双轨命令使用、帮助自省方式、安全规则。当用户首次配置 wps365-cli CLI、遇到认证问题、需要切换身份类型、管理 spec 文件，或不确定某命令语法时触发。其他业务域 skill 在开始执行前都应先读取本文件。"
metadata:
  requires:
    bins: ["wps365-cli"]
---

# WPS365-CLI 共享基础

本技能描述 wps365-cli CLI 的基础能力与全局约定。所有业务域 skill 都应在执行前先读取本文件。

## 安装与版本

```bash
wps365-cli version          # 查看当前版本
wps365-cli update --check   # 与 CDN latest 比对（不下载）
wps365-cli update           # 落后则下载并替换当前二进制
wps365-cli --help           # 查看顶层命令列表
wps365-cli <domain> --help  # 查看某域下的命令
```

升级二进制后若新命令找不到，再执行 `wps365-cli spec update -y`（或用 skills 包内 `spec/` 覆盖）。不要用重跑 `install.sh` 作为默认升级路径。

## 认证

WPS365 使用 OAuth2，支持两类身份：

| 身份类型 | 标识 | 适用场景 |
|---------|------|---------|
| delegated（用户授权） | `--token-type delegated` | 访问用户自己的资源（日历、文档等） |
| app（应用身份） | `--token-type app` | 应用级操作，以应用名义访问 |

未显式指定时，命令按 OpenAPI `security` 规则决定默认身份，兼容多种时优先选 `delegated`。

### 认证命令

```bash
# 1. 首次配置：写入 client_id、client_secret（可选 redirect_uri）
wps365-cli auth setup --client-id "AK20..." --client-secret "sk-..." --redirect-uri "http://127.0.0.1:53682/callback"

# 2. 用户授权登录（delegated）—— 需要先完成 setup；--scopes 可多次 login 累积
wps365-cli auth login --scopes "kso.calendar.read,kso.calendar.readwrite"
# 其他域示例（按业务替换 scope，以 --help 与 spec 为准）：
# wps365-cli auth login --scopes "kso.mailbox.read,kso.mailbox.readwrite"

# 3. 查看认证状态
wps365-cli auth status

# 4. 主动刷新 token
wps365-cli auth refresh              # 刷新所有已存在的 token
wps365-cli auth refresh --delegated  # 仅刷新 delegated token

# 5. 退出登录
wps365-cli auth logout
```

### 重要认证规则

- `auth login` **必须**显式传入 `--scopes`，不提供则报错。
- `auth login` 的 scope 是累积的：本次请求会与已有授权取并集。
- 若缺少 `redirect_uri`（`auth setup` 未配置也未在命令行传入），`auth login` 无法发起用户授权。
- 多次 `auth login` 不同 scope 是安全的，不会清除已有授权。

### Agent 代理发起认证（无头场景）

当你作为 AI agent 需要帮用户完成认证时，在**后台**运行命令，读取输出，从中提取授权链接并发给用户：

```bash
# 发起用户授权（该命令阻塞直到用户完成授权或过期）
wps365-cli auth login --scopes "kso.calendar.read"
# 从输出中找到授权 URL，将其发送给用户让其在浏览器中打开
```

### 权限不足处理（403、缺少 scope、应用无权限）

回答用户或编写排错步骤时，应**区分身份**，并写出可复制的 CLI 形式（不要只写「去补权限」而不给命令名）。

**delegated（用户授权 token，默认常见）**

1. 核对当前身份与 scope：`wps365-cli auth status`。
2. 缺 scope 时执行：**`wps365-cli auth login --scopes "缺失的scope1,缺失的scope2"`**（具体 scope 以错误信息、接口文档或域 skill 为准），将命令输出中的授权 URL 交给用户在浏览器完成授权，再重试业务命令。

**app（应用身份 / client credentials）**

- 权限绑定在 **WPS365 开发者控制台/后台的应用配置**上：若该应用未开通某 API 或某权限，**必须在开发者后台为应用开通**；**CLI 无法代替在后台点击开通权限**，也无法绕过未开通的权限。
- **这不等于「CLI 不能创建/绑定应用」**：创建或绑定应用、写入 `client_id`/`client_secret` 用 **`wps365-cli config init`**（见 `../wps365-getting-started/SKILL.md`）。「后台开通」指的是应用上的 API/scope 能力，不是建应用本身。
- 排错时明确告知：缺的是应用能力权限时，需应用负责人在开发者后台开通；缺的是本地绑定/凭证时，走 `config init` / `auth setup`。

**易混点**

- 不要把 delegated 与 app 的修复路径混为一谈：delegated 走 `auth login --scopes`；app 走开发者后台开通。
- **还有第三层：企业套餐权益**（见下）。`ErrPrivileges: interface_*` **不是** OAuth scope，补 `auth login --scopes` / 开应用权限都解决不了。

### 企业套餐权益不足（`403000001` / `ErrPrivileges`）

若响应类似：

```json
{
  "code": 403000001,
  "message": "kso: PermissionDenied err: ErrPrivileges: interface_company_doc"
}
```

这是**权益网关**校验：当前企业套餐**没有**该业务接口对应的开放能力权益。`ErrPrivileges:` 后面的枚举是权益点，**与** `kso.*` OAuth scope、应用「能力权限」不是同一层。

较新版本 CLI 会在原错误后追加一行 `hint: 企业套餐权益不足...`（含权益点与升套餐指引）。若已有该 hint，**直接按 hint 转告用户**，不要改说成「去开发者后台开企业文档接口」。

**Agent 处理（必做）：**

1. 识别 `code=403000001`、文案含 `ErrPrivileges` / `interface_` / `saas_`，或 CLI 输出的 `hint: 企业套餐权益不足`。
2. **不要**引导用户反复 `auth login`、换 `--token-type`、或只去开应用 scope / 「开发者后台开接口」。
3. 明确告知用户：请联系**企业管理员**开通 **【商业高级版】** 或 **【商业旗舰版】** 企业套餐权益（按企业实际采购/升级路径办理）；权益生效后再重试原命令。
4. 可把报错里的权益点原样转告管理员（例如 `interface_company_doc`）。

常见权益点（完整列表以网关为准；下列为已知枚举）：

| 权益点 | 含义（便于转告管理员） |
|--------|------------------------|
| `interface_company_doc` | 云文档开放能力（如 `drive list` 等）；需 **商业高级版及以上** |
| `interface_team_manage` | 文档库 / 团队文档相关开放能力 |
| `interface_team_permission_setting` | 团队权限设置相关 |
| `interface_corp_space` | 企业空间相关 |
| `interface_update_user_schedule` | 更新用户日程相关 |
| `interface_contacts_management` | 通讯录管理相关 |
| `interface_contacts_visibility_setting` | 通讯录可见性设置相关 |
| `interface_customize_address_fields` | 自定义通讯录字段相关 |
| `interface_query_manage_mailbox` | 管理邮箱查询相关 |
| `saas_im_aisearch` | IM AI 搜索相关 |

> 示例：`interface_company_doc` → 云文档开放接口需要企业具备 **商业高级版**（或更高，如商业旗舰版）套餐权益，体验版/未开通对应权益时会 403。

## 环境变量

| 变量 | 作用 |
|------|------|
| `WPS365_CONFIG_DIR` | 覆盖默认配置目录（Linux: `~/.config/wps365-cli`，macOS: `~/Library/Application Support/wps365-cli`） |
| `WPS365_ACCESS_TOKEN` | 直接注入 access token，最高优先级，适用于 CI/无头环境，注入后跳过本地 token 文件 |
| `WPS365_KEYRING_BACKEND` | 凭证后端：`auto`（默认）、`keychain`（系统 keychain）、`file`（加密文件） |
| `WPS365_KEYRING_PASSWORD` | `file` 后端的加密密码；未设置时回退使用 `client_secret` |
| `WPS365_API_BASE` | 覆盖业务 API base URL（不影响 OAuth 端点） |

## 全局输出格式

所有业务命令都继承全局 `-o, --output` 参数，用于指定输出格式：

```bash
wps365-cli <command> --output json
wps365-cli <command> --output yaml
wps365-cli <command> --output table
wps365-cli <command> --output tsv
```

说明：

- `--output` 在 WPS365 CLI 中表示**输出格式**，不是通用“保存到文件”参数。
- 若某个具体命令支持把结果保存到本地文件，请以该命令自己的 `--help` 为准，例如 `drive file download` 一类命令可能有业务专用输出参数。

## 双轨命令：精装命令 vs api 兜底

WPS365 CLI 提供两类命令入口：

**精装命令**（优先使用）：
```bash
wps365-cli calendar event list primary
wps365-cli im message send --to u1 --text "hello"
```

**api 兜底命令**（精装命令缺失时使用）：
```bash
wps365-cli api get /v7/calendars
wps365-cli api post /v7/messages/create --data '{"receiver_id": "xxx", "msg_type": "text"}'
wps365-cli api post /v7/messages/batch_create --file body.json
```

`api` 命令支持 `get`、`post`、`put`、`patch`、`delete`、`head`；路径为相对 API path，如 `/v7/calendars`。

## Spec 文件管理

官方命令定义（`api.yaml` / `curated.yaml`）落在本机配置目录的 `spec/` 下（路径见 `wps365-cli config path`，其下为 `spec/api.yaml`、`spec/curated.yaml`）。首次运行可能从 CDN 拉取；**已安装过旧版的存量客户升级后，本地几乎一定仍是旧 YAML**。

### Agent 必做：升级 / 换 skills 包后刷新本地 spec

在跑任何业务命令前，若出现下列任一情况，**必须先刷新本地 spec，再继续**：

- 用户刚升级 CLI，或刚安装/解压新的 `wps365-skills-*.zip`
- 命令找不到、参数/行为与当前 skill 文档不一致
- 发消息报 `--token-type=delegated is incompatible with operation security`，或未指定却总是强制走 app
- `airpage` / `airsheet` / `drive doclib` 等新域命令缺失

**优先用 skills 包内附带的 `spec/` 覆盖本机**（与当前 skill/CLI 能力对齐；CDN 可能滞后）：

```bash
# <SKILLS_PKG> = 本 skills 包解压后的 wps365-skills/ 根目录（内含 spec/api.yaml、spec/curated.yaml）
SPEC_DIR="$(wps365-cli config path)/spec"
mkdir -p "$SPEC_DIR"
cp "<SKILLS_PKG>/spec/api.yaml" "<SKILLS_PKG>/spec/curated.yaml" "$SPEC_DIR/"
wps365-cli spec status
```

若包内**没有** `spec/` 目录，再退回 CDN：

```bash
wps365-cli spec update -y
wps365-cli spec status
```

> Agent 注意：只升级 CLI 二进制、不覆盖 `spec/`，**不能**修好 security / 新命令。覆盖前可向用户说明将更新本地命令定义文件；不要把 `api.yaml` 全文贴进对话。

## 帮助与自省

```bash
# 查看某域下所有子命令
wps365-cli calendar --help
wps365-cli im --help

# 查看某命令的参数详情
wps365-cli calendar event create --help
wps365-cli im message send --help
```

完整的生成文档位于仓库 `docs/generated/` 目录（如 `wps365_calendar_events_create.md`）。

## 配置管理

```bash
wps365-cli config path           # 查看配置目录路径
wps365-cli config get <key>      # 读取配置项
wps365-cli config set <key> <value>  # 设置配置项
wps365-cli config unset <key>    # 删除配置项
```

## 安全规则

- **禁止输出密钥**：不得将 `client_secret`、`access_token`、`refresh_token` 输出到终端明文或写入日志。
- **写入/删除操作前必须确认用户意图**：涉及 `create`、`update`、`delete` 等命令，执行前向用户确认。
- **批量操作需说明影响范围**：涉及批量写入或删除时，先报告将要影响的数量和范围。
- **使用 `--dry-run` 预览**：对不确定影响的命令，优先用 `--dry-run` 试运行。
- **不得擅自发起持续性订阅**：不使用 watch 类命令在用户未知情的情况下持续监听数据。
- **禁止全量拉取企业通讯录组织树/成员**：不要执行 `dept list <root_id>`、`dept member list <root_id> --recursive --all`，也不要用 `api` 递归调用 `/v7/depts/.../children` 或 `/v7/depts/.../members` 导出全公司部门与人员。找人用 `user search`；查某人部门用 `user dept list <USER_ID>`。
