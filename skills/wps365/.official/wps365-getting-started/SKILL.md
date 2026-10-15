---
name: wps365-getting-started
description: "WPS365 CLI 快速接入总入口：安装并验证 wps365-cli、私有化环境地址配置（api-base）、一键绑定应用（config init）或通过开发者控制台创建应用（provider bootstrap）、OAuth 认证（auth setup/login，含 --device 无头登录）、验证跑通（user me），并导航到各业务域能力与 api 兜底。当客户首次接入 wps365-cli、需要从零安装配置认证、跑第一个命令、切换公有云/私有化环境，或不确定该用哪个业务 skill 时触发。"
metadata:
  requires:
    bins: ["wps365-cli"]
---

# WPS365 CLI 快速接入

本技能是客户接入 wps365-cli 的**总入口**：从安装到跑通第一个命令，再导航到具体业务能力。深入的业务操作请转对应业务域 skill（见文末「能力地图」）。

## Agent 执行指引（先读这段）

**第一步永远是探测状态，跳过已完成的步骤，避免重复操作：**

```bash
wps365-cli version              # 无输出 → 先装（见步骤 1）
wps365-cli update --check       # 落后 CDN latest → 再跑 wps365-cli update
wps365-cli config get api-base  # 私有化且未配 → 先配（见步骤 2）；公有云可忽略
wps365-cli auth status          # 已登录 → 直接用；未登录 → 按下方登录
```

**旧版升级 / 新 skills 包接入后（Agent 必做）：** 存量客户本机 `$(wps365-cli config path)/spec/` 往往仍是旧 `api.yaml` / `curated.yaml`。只换 CLI 不够——**必须先覆盖刷新 spec，再跑业务命令**。

```bash
# 1) 优先：用本 skills 包内 spec/ 覆盖（与包内 CLI/文档一致；CDN 可能滞后）
SPEC_DIR="$(wps365-cli config path)/spec"
mkdir -p "$SPEC_DIR"
cp "<SKILLS_PKG>/spec/api.yaml" "<SKILLS_PKG>/spec/curated.yaml" "$SPEC_DIR/"
# <SKILLS_PKG> = 解压后的 wps365-skills/ 目录

# 2) 包内无 spec/ 时再走 CDN
wps365-cli spec update -y

wps365-cli spec status
```

典型症状：发消息报 `delegated is incompatible with operation security`、新命令找不到、行为与 skill 文档不符——先按上面覆盖 `spec/`，不要反复改 `--token-type`。

**首次接入 / 重新初始化（公有云，优先 `config init`）：**

```bash
wps365-cli config init                 # 浏览器建/绑应用并自动写凭证
# 重新初始化或换应用：
wps365-cli config init --new --force   # 新建并覆盖本地绑定
# 或：wps365-cli config init --force   # 选已有应用并覆盖

wps365-cli auth login --device --scopes "kso.user_base.read"   # 设备码登录，必须带所需 scope
wps365-cli user me              # 验证，成功即接入完成
```

> **Agent 禁令：** 不要说「CLI 无法创建应用、必须先去开发者后台手动建应用再把 secret 交给我」。公有云用 **`config init` / `config init --new`** 即可在浏览器里创建或绑定应用并写入凭证。`auth setup` 仅用于**已有** AK/SK。找不到 `provider bootstrap` **不等于**不能建应用（见步骤 3）。

> **登录一律用 `--device`**：不要用不带 `--device` 的 `auth login`，那会走授权码流程、自动打开浏览器并监听本地回调端口。**`--device` 必须带 `--scopes`**：device 流程按你传入的 scope 申请授权，**不带 scope 会导致 `granted []`**，后续命令报 `token missing required scopes`。`kso.user_base.read` 是 `user me` 的最小 scope；按业务再追加域 scope（如 `kso.drive.readwrite,kso.file_search.readwrite`）。scope 只能申请应用在开发者后台**已开通**的项；申请到未开通/拼错的 scope（如 `kso.user.readwrite`）会报 `invalid_scope`。

> **设备码登录必须跑到完成**：`auth login --device` 靠进程轮询领取 token（非浏览器回调）。启动后把链接展示给用户并**保持进程存活**，等它自行成功退出；切勿检查一次 `auth status` 就终止它，否则用户授权后无人领取、token 永远拿不到。
>
> **手机扫码：** `config init` 与 `auth login --device` 都在终端 stderr 内嵌 ASCII 码。若需要图片：`wps365-cli auth qrcode --file qr.png "<验证 URL>"`。**不要**把全局 `-o/--output` 当成文件路径（那是 json|yaml|table 格式）；PNG 路径用 `--file`。相对当前工作目录，禁止 `..` 与绝对路径。
>
> 私有化 / 已有凭证 / 程序化建应用等场景见下方分步详解；排错见文末「FAQ」。

---

## 步骤 1：安装并验证

先验证是否已安装：

```bash
wps365-cli version
```

若提示「找不到 wps365-cli」，按平台安装：

```bash
# macOS / Linux / Windows(Git Bash)
curl -fsSL https://raw.githubusercontent.com/wps365-open/cli/main/install.sh | bash
```

```powershell
# Windows PowerShell
irm https://raw.githubusercontent.com/wps365-open/cli/main/install.ps1 | iex
```

> **离线/内网**：若本技能包内含 `bin/` 目录（预置了各平台 CLI 归档），无需联网下载，直接解压与本机匹配的归档即可：
> `aarch64-apple-darwin`=Apple 芯片 Mac · `x86_64-apple-darwin`=Intel Mac · `*-unknown-linux-gnu`=Linux · `*-pc-windows-gnu`=Windows。
> 例：`tar -xzf bin/wps365-cli-*-aarch64-apple-darwin.tar.gz`（Windows 用对应 `.zip`），将解出的 `wps365-cli` 移到 `PATH` 目录或用绝对路径调用。

安装后仍找不到命令：说明安装目录不在 `PATH`。把安装目录写入 `~/.zshrc`（或 `~/.bashrc`）后**重启终端/IDE**；不便改 `PATH` 时，所有命令改用绝对路径 `/完整路径/wps365-cli …`。

---

## 步骤 2：确认环境（公有云 / 私有化）

- **公有云**：使用官方默认地址，**无需配置**，直接进入步骤 3。
- **私有化部署**：所有出网操作前**必须**先配置 API 网关地址，否则会打到错误的 host。

```bash
# 查看当前 API 网关地址
wps365-cli config get api-base

# 设为私有化网关（注意 key 是 api-base，不是 api-base-url）
wps365-cli config set api-base "https://<你的网关host>"
```

> 也可用环境变量 `WPS365_API_BASE` 临时覆盖（优先级高于配置文件），适合 CI/多环境切换：
> `export WPS365_API_BASE="https://<你的网关host>"`

私有化环境若本机 CLI **有** `provider bootstrap`（见步骤 3 方式 C），创建应用时还需指定开发者控制台地址。禁止臆造 host，须向用户索取其私有化实际地址。无 bootstrap 时：先配 `api-base`，再用 **`config init`**（若该部署支持）或 **`auth setup`** 写入已有凭证。

---

## 步骤 3：绑定应用 + 认证

WPS365 使用 OAuth2。先要有一个应用（`client_id`/`client_secret`），再完成用户授权登录。

> **默认用方式 A。** 只有用户已持有 AK/SK、或 `config init --help` 不可用时，才退到方式 B。不要因找不到 `provider bootstrap` 就声称「CLI 不能创建应用」。

### 方式 A：一键绑定 / 重新初始化（推荐，公有云默认）

浏览器完成应用**创建或选择**，并自动写入凭证（CLI **具备**建/绑应用能力）：

```bash
wps365-cli config init                 # 交互式：浏览器登录 → 选择/创建应用 → 写入 client_id/secret
wps365-cli config init --new           # 直接新建应用
wps365-cli config init --app-id "<APP_ID>"   # 绑定已有应用
wps365-cli config init --new --force   # 重新初始化：新建并覆盖本地已有绑定
wps365-cli config init --force         # 重新初始化：覆盖绑定（可选已有应用）
```

以本机 `wps365-cli config init --help` 为准（应能看到 `--new` / `--force` / `--app-id`）。

### 方式 B：已有凭证，手动配置

仅当用户**已经**有 `client_id`/`client_secret`（或不走浏览器绑定时）使用——**不是**「CLI 不能建应用」时的唯一出路：

```bash
wps365-cli auth setup           # 交互式引导写入凭证
# 或非交互：
wps365-cli auth setup --client-id "AK..." --client-secret "sk-..." \
  --redirect-uri "http://localhost:18365/callback"
```

### 方式 C：`provider bootstrap`（可选；部分构建才有）

先探测：`wps365-cli provider bootstrap --help`。若提示 unknown command，**本机 CLI 无此命令**——改用方式 A / B，**不要**据此推断「无法创建应用」。

若 `--help` 可用，可用控制台 `wps_sid`（Cookie）或账号登录程序化建应用（含部分私有化场景）：

```bash
wps365-cli provider bootstrap --dry-run --scenario drive,aidocs
wps365-cli provider bootstrap --scenario drive,aidocs \
  --api-base-url "https://<你的网关host>" \
  --console-base-url "https://<你的控制台host>" \
  --devconsole-sid "<wps_sid值>"
wps365-cli provider bootstrap --scenario drive --console-login
```

> `--scenario`（`-b`）按场景决定申请哪些 scope；`--devconsole-sid` 也可用环境变量 `WPS365_DEVCONSOLE_SID` 提供。

### 完成登录授权

凭证就绪后进行用户授权。**设备码流程与浏览器授权码流程都必须用 `--scopes` 传入所需权限**——device 流程按传入的 scope 申请，**不带 scope 会导致 `granted []`**、后续命令报 `token missing required scopes`：

```bash
# 设备码流程（无头 / 有浏览器均可用）：带上所需 scope
wps365-cli auth login --device --scopes "kso.user_base.read,kso.drive.readwrite"
```

> **设备码登录必须跑到完成**（要点见顶部「Agent 执行指引」）：进程轮询领取 token，须保持存活直到自行成功退出，切勿过早终止；被杀或 `device_code` 超时（`device code expired`）需重新运行。详细排错见文末「FAQ」。

> **登录一律用 `--device`。** 不要用不带 `--device` 的 `auth login`——那会走**授权码流程**：自动打开浏览器、构造 `response_type=code` 链接并监听本地回调端口（如 `localhost:18365/callback`），在 agent/无头/端口受限场景容易失败或产生非预期的浏览器弹窗。
>
> 仅当确实无法使用设备码流程时，才用授权码流程作为备选：
>
> ```bash
> wps365-cli auth login --scopes "kso.user_base.read,kso.calendar.read"
> ```

`--scopes` 只能申请应用在开发者后台**已开通**的项，scope 名以业务域 skill 与后台配置为准。`auth login` 的 scope **累积生效**（与已有授权取并集），多次登录补不同 scope 是安全的，不会清除已授权项。遇到 `invalid_scope: The requested scope '...' is not allowed`：说明该 scope 拼错或应用未开通——**去掉/改正那一个** scope，或先在开发者后台为应用开通再申请，**不要删掉全部 scope**（删空会变成 `granted []`）。

---

## 步骤 4：验证跑通

```bash
wps365-cli auth status     # 查看身份、scope、过期时间
wps365-cli user me         # 拉取当前用户，返回成功即接入完成
```

---

## 认证要点

| 身份模式 | 标识 | 适用场景 | 获取方式 |
|---------|------|---------|---------|
| delegated（用户授权） | `--token-type delegated` | 用户态接口（我的日历/文档等） | `auth login --device --scopes "..."` |
| app（应用身份） | `--token-type app` | 服务端/应用态接口 | 直接执行命令，必要时加 `--token-type app` |

命令按底层 OpenAPI `security` 自动选身份，`--token-type` 可显式覆盖；delegated 不可用时自动回退到 app。

常用认证命令：

```bash
wps365-cli auth token            # 输出当前 access token（--app 输出应用身份 token）
wps365-cli auth refresh --delegated   # 手动刷新（或 --app）
wps365-cli auth logout           # 退出登录（保留凭证，可直接重新 login）
wps365-cli auth clean --force    # 完全重置：清除所有 token/凭证/自动密钥
```

**403 / 缺 scope 处理（区分身份）：**

- **delegated**：`auth status` 核对后 `auth login --device --scopes "缺失的scope"` 补授权（scope 累积生效），把输出中的设备码链接交用户在浏览器完成授权，再重试。
- **app**：权限绑定在开发者控制台的应用配置上，**必须由管理员在后台为应用开通**，CLI 无法绕过。
- **企业套餐权益（`403000001` / `ErrPrivileges: interface_*`）**：不是 OAuth scope。引导用户找**企业管理员**开通 **【商业高级版】** 或 **【商业旗舰版】**；详见 `../wps365-shared/SKILL.md`「企业套餐权益不足」。示例：`interface_company_doc` = 云文档开放能力，需商业高级版及以上。

**CI / 无头注入凭证（环境变量）：**

```bash
export WPS365_CLIENT_ID="<client-id>"
export WPS365_CLIENT_SECRET="<client-secret>"
# 或直接注入 access token，跳过本地存储与刷新：
export WPS365_ACCESS_TOKEN="<token>"
```

---

## 双轨命令体系

**精装命令**（优先，语义化参数）：

```bash
wps365-cli calendar event list primary
wps365-cli im messages send --to "u1" --to "u2" --text "hello"
```

**api 兜底**（精装未覆盖的接口，全量 API）：

```bash
wps365-cli api get "/v7/users/current"
wps365-cli api post "/v7/messages/batch_create" --data '{ ... }'
```

`api` 支持 `get|post|put|patch|delete|head`；路径为相对 API path。

**自省帮助**（不确定语法时首选）：

```bash
wps365-cli --help                 # 顶层业务域列表
wps365-cli <domain> --help        # 某域子命令
wps365-cli <domain> <cmd> --help  # 参数详情
```

---

## 能力地图与业务 skill 导航

| 业务域 | 顶层命令 | 深入使用请读 |
|--------|---------|-------------|
| 基础/认证/环境 | `auth` `config` `spec` `provider` | `../wps365-shared/SKILL.md` |
| 云文档 / 文档团队 | `drive`（含 `drive doclib`） | `../wps365-drive/SKILL.md` |
| 智能文档 | `airpage` | `../wps365-airpage/SKILL.md` |
| 智能表格 | `airsheet` | `../wps365-airsheet/SKILL.md` |
| 即时通讯 | `im` | `../wps365-im/SKILL.md` |
| 日历/会议 | `calendar` `meeting` | `../wps365-calendar/SKILL.md` · `../wps365-calendar-insert/SKILL.md` · `../wps365-meeting/SKILL.md` |
| 邮箱 | `mail` | `../wps365-mail-core/SKILL.md` |
| 多维表 | `dbsheet` | `../wps365-dbsheet-records/SKILL.md` · `../wps365-dbsheet-schema/SKILL.md` |
| 通讯录/用户 | `user` | `../wps365-contacts/SKILL.md` · `../wps365-user/SKILL.md` |
| WorkBuddy / MCP 接入 | `mcp` | `../wps365-mcp/SKILL.md`（企业 365；不要与 kdocs 个人连接器混用） |

各业务 skill 内有该域的 scope 清单与命令示例；具体 scope 以业务 skill 与 `--help` 为准。

---

## 输出、预览与排错

```bash
-o json|yaml|table|tsv|ndjson|csv   # 输出格式（全局 -o/--output）
--dry-run                            # 只打印请求不发送，先预览
--jq '<filter>'                      # 内置 jq 过滤
--quiet                              # 仅输出数据与错误
```

**退出码：** `0` 成功 · `1` API 错误 · `2` 认证 · `3` 参数 · `4` spec · `5` 内部错误。

**spec 管理：** 命令定义在本机 `$(wps365-cli config path)/spec/`。**存量客户升级 CLI 或换用新 skills 包后，Agent 必须先刷新该目录**，再执行业务命令：

```bash
# 优先：覆盖 skills 包内 spec/
cp "<SKILLS_PKG>/spec/api.yaml" "<SKILLS_PKG>/spec/curated.yaml" "$(wps365-cli config path)/spec/"
# 包内无 spec/ 时：
wps365-cli spec update -y
wps365-cli spec status
```

---

## 常见问题（FAQ）

**Q：刚升级了 CLI / skills 包，新命令找不到、发消息只能走 app、或行为与文档不一致？**

本机 `spec/api.yaml`（及 `curated.yaml`）仍是旧版。Agent **优先**用 skills 包内 `spec/` **覆盖**到 `$(wps365-cli config path)/spec/`；包内没有再执行 `wps365-cli spec update -y`。然后用 `wps365-cli spec status` 核对并重试。只升级二进制、不覆盖 spec，无法修复 security / 新命令。

**Q：重新初始化 / 换应用时，Agent 说「CLI 不能创建应用，必须去后台手动建」？**

这是误判。公有云请用 **`wps365-cli config init --new --force`**（或 `config init --force`）在浏览器创建/绑定并覆盖本地凭证，再 `auth login --device --scopes "..."`。`auth setup` 只用于已有 AK/SK。找不到 `provider bootstrap` 时改用 `config init`，不要要求用户先贴 secret。

**Q：config init 一直显示 Waiting for binding？**

请确认浏览器侧已完成全部步骤，尤其是最后的 授权确认。仅创建/绑定应用而未授权，CLI 会持续 pending 直到会话过期。

**Q：config init 和 auth setup 有什么区别？**

| 维度 | config init | auth setup |
|------|-------------|------------|
| 适用场景 | 首次使用、快速上手 | 已有凭证、手动管理 |
| 操作方式 | 浏览器引导，自动获取 AK/SK | 交互式输入或环境变量注入 |
| 存储位置 | 相同（config.json + 安全存储） | 相同 |

**Q：`auth login --device` 已在浏览器完成授权，为什么迟迟拿不到 token？**

设备码流程不是浏览器回调，token 只能由**仍在运行的登录进程轮询领取**（约每 5 秒一次），领到后进程自行成功退出。若那个 `auth login --device` 进程已被终止或 `device_code` 已超时（`device code expired`），浏览器里批准的授权就无人领取，token 永远不会自动到本地。处理：确认没有 `auth login` 进程存活（`ps aux | grep "auth login"`）后，**重新运行** `wps365-cli auth login --device`，用新链接在浏览器完成「授权确认」，并**保持该进程运行直到它自行退出**，再用 `wps365-cli auth status` 确认。agent 编排务必把该命令当作需等待完成的任务，不要过早终止。

**Q：调用命令报 token missing required scopes: need one of [...], granted []？**

登录时没带（或带空）`--scopes`，导致未授予任何权限。device 流程按传入的 scope 申请，必须显式带上，例如 `user me` 至少需要 `kso.user_base.read`：

```bash
wps365-cli auth login --device --scopes "kso.user_base.read,kso.drive.readwrite,kso.file_search.readwrite"
```

scope 累积生效，可多次登录补齐。补授权后重试原命令即可。

**Q：登录报 invalid_scope: The requested scope '...' is not allowed？**

是**某一个** scope 拼错或应用未在开发者后台开通（例如把 `kso.user_base.read` 误写成 `kso.user.readwrite`）。处理：从 `--scopes` 中**去掉/改正那一个**错误 scope，或先在开发者后台为应用开通该权限再申请；**不要删掉全部 scope**，删空会导致 `granted []`、后续命令报缺 scope。

**Q：权限申请后为什么没有生效？**

权限申请后需要完成「创建版本 → 申请发布 → 企业管理员审批」的完整流程才会生效。仅申请权限而不提交版本审批，权限会一直处于「待提交审核」状态。

**Q：调用报 `403000001` / `ErrPrivileges: interface_company_doc`（或其它 `interface_*` / `saas_*`）？**

这是**企业套餐权益**未开通，不是登录 scope 不够。权益网关按业务点校验（如 `interface_company_doc` = 云文档开放能力，需 **商业高级版及以上**）。Agent 应引导用户联系**企业管理员**开通 **【商业高级版】** 或 **【商业旗舰版】**，不要反复 `auth login`。其它已知权益点见 `../wps365-shared/SKILL.md`。

**Q：通讯录接口返回空数据或权限错误？**

部分 API（尤其是通讯录相关接口）除了需要「能力权限」外，还需要配置「可用范围」和「数据权限」。请在应用详情页的 权限管理 中检查。

**Q：CLIENT_SECRET 泄露了怎么办？**

立即在开发者后台「应用凭证」区域点击「重置」生成新密钥，旧密钥立即失效。然后重新执行 `wps365-cli config init` 或 `wps365-cli auth setup` 配置新凭证。

---

## 安全规则

- 禁止明文输出 `client_secret` / `access_token` / `refresh_token`。
- `create` / `update` / `delete` 及批量写操作前，先向用户确认意图，不确定时用 `--dry-run` 预览。
- 批量写/删前报告将影响的数量与范围。
- 私有化环境禁止臆造 host，须使用用户提供的实际网关/控制台地址。
- **禁止全量拉取企业通讯录**：不要执行 `wps365-cli dept list <root_id>`、`wps365-cli dept member list <root_id> --recursive --all`，也不要用 `api` 递归遍历 `/v7/depts/.../children` 或 `/v7/depts/.../members`。找人用 `user search`；查某人部门用 `user dept list <USER_ID>`。
