---
name: wps365-drive
description: "WPS 365 云文档：盘管理、文件与文件夹的增删改查、搜索、本地上传、文档内附件上传（airpage/airsheet 内嵌图用 attachment_id）、下载、权限管理、文档库/团队文档（drive doclib）。当用户需要创建文档、上传文件、管理云文档、查询文档团队时触发。智能文档/智能表格分别走 wps365-airpage / wps365-airsheet。"
metadata:
  requires:
    bins: ["wps365-cli"]
---

# 云文档 (drive)

> **前置条件：** 首次接入先读 `../wps365-getting-started/SKILL.md`；再读 `../wps365-shared/SKILL.md` 了解认证、全局参数和安全规则。
>
> 旧版升级到含 `drive doclib` 精装命令的 CLI 后，先执行 `wps365-cli spec update -y`。找不到 `drive doclib` 时优先刷新 spec。

## 授权模型

| 授权类型 | 操作范围 | 登录方式 |
|---------|---------|---------|
| **delegated / app** | 盘管理、文件操作、搜索、上传 | `auth login --device --scopes "..."` 或直接执行命令并加 `--token-type app` |
| **app only** | AI 文档处理 | 直接执行目标命令并加 `--token-type app` |

### 登录示例

登录一律用 `--device`，且必须带 `--scopes`（省略会导致 `granted []`）：

```bash
wps365-cli auth login --device --scopes "kso.drive.readwrite,kso.file.readwrite,kso.doclib.read,kso.deleted_file.readwrite,kso.file_search.readwrite,kso.coop_files.readwrite"
```

插文档内图片时务必带上 **`kso.coop_files.readwrite`**。

## OAuth Scope

| Scope | 权限 |
|-------|------|
| `kso.drive.readwrite` | 管理盘与文件（文件夹 + 文件 CRUD / 上传下载） |
| `kso.doclib.read` | 查询文档库/团队文档列表 |
| `kso.file.readwrite` | 文件管理；创建智能文档/智能表格时内部 `request_upload` 也需要 |
| `kso.airpage.readwrite` | 创建智能文档（airpage） |
| `kso.airsheet.readwrite` | 创建智能表格（airsheet） |
| `kso.coop_files.readwrite` | 文档内附件上传（插图用 `attachment_id`，非盘上传） |
| `kso.deleted_file.readwrite` | 管理回收站 |
| `kso.file_search.readwrite` | 搜索文件 |

> **注意：** 创建**智能文档**（airpage）需要 `kso.airpage.readwrite`，创建**智能表格**（airsheet）需要 `kso.airsheet.readwrite`；这些 scope 需在 WPS365 开发者后台为应用单独开通。创建 `.otl` / `.ksheet` 还会走内部 `request_upload`，须同时申请 **`kso.file.readwrite`**。如果未开通，可先创建**文件夹**存放文档。
>
> `drive list` / `drive doclib list` 还依赖企业套餐权益（`interface_company_doc` / `interface_team_manage` 等）。若报 `403000001` / `ErrPrivileges: ...`，引导用户找企业管理员开通 **商业高级版** 或 **商业旗舰版**（与 OAuth scope 无关）。详见 `../wps365-shared/SKILL.md` / getting-started FAQ。

## 核心流程

### 获取盘 ID

大部分文件操作需要 `drive_id`。获取当前用户的盘：

```bash
wps365-cli drive list --allotee-type user
# → data.items[].id 即为 drive_id
```

### 查询自己加入的文档团队

不要用通讯录 `GET /v7/groups`，也不要把 `drive list --allotee-type group` 当主路径。

```bash
wps365-cli drive doclib list --page-size 20
# → data.items[].drive.id 为盘 ID（doclib 没有顶层 drive_id）
# → data.items[].group 为团队信息
```

列某个团队根目录下的文件（两步，没有单接口）：

```bash
wps365-cli drive file list <DRIVE_ID> 0 --page-size 50
```

列出全员团队中的文件：先 `drive doclib list --page-size 20`，客户端筛 `data.items[].group.type == "whole"`（不是 `org_normal`；公开 OpenAPI 没有「全员」字样），再对筛出的 `items[].drive.id` 执行 `drive file list <drive_id> 0 --page-size 50`。不要用 `GET /v7/doclib/search`。

`drive doclib get --drive-id <DRIVE_ID>` 只取库元信息，不是列文件。

### 创建文件/文件夹

```bash
wps365-cli drive file create <DRIVE_ID> <PARENT_ID> \
  --name "文件名" \
  --file-type <类型>
```

**文件类型（file-type）：**

| 值 | 说明 |
|----|------|
| `folder` | 文件夹 |
| `file` | 普通文件 |
| `shortcut` | 快捷方式 |

> `<PARENT_ID>` 使用 `0` 表示盘的根目录。

**示例：**

```bash
# 创建文件夹
wps365-cli drive file create dr_abc 0 \
  --name "项目资料" \
  --file-type folder
```

### 创建智能文档（airpage）

智能文档走独立精装命令，需要 `kso.airpage.readwrite` scope。细节见 [wps365-airpage](../wps365-airpage/SKILL.md)。

```bash
wps365-cli airpage create \
  --drive-id <DRIVE_ID> --parent-id 0 --name "会议待办列表" \
  --template-id "" --on-name-conflict rename
```

`--template-id ""` 表示空白文档。创建**智能表格**见 [wps365-airsheet](../wps365-airsheet/SKILL.md)。

### 列表 / 详情 / 搜索 / 下载 / 上传

```bash
wps365-cli drive file list <DRIVE_ID> <PARENT_ID> --page-size 50
wps365-cli drive file get <DRIVE_ID> <FILE_ID>
wps365-cli drive file search --keyword "季度报告"
wps365-cli drive file download <DRIVE_ID> <FILE_ID>
# 本地上传到父目录（docx/xlsx/pptx 等）；默认 ≤4MiB 单段上传，更大自动分块并行 PUT
wps365-cli drive file upload <DRIVE_ID> <PARENT_ID> /path/to/file.docx
wps365-cli drive file upload <DRIVE_ID> <PARENT_ID> ./大表.xlsx --simple-max-bytes 4194304 --upload-workers 8
```

上传为 **原生子命令**（非 `specs/curated.yaml`）：`wps365-cli drive file upload --help` 查看 `--name`、`--file-id`、`--on-name-conflict`、`--simple-max-bytes` 等。若环境对大文件所需的 **`multipart_upload_tasks/.../sign`** 未开放，大文件路径会失败，需对照该部署的 OpenAPI 或临时仅用简单上传受限允许的大小。

**CLI 能力说明：** 以本机 `wps365-cli drive file upload --help` **能打出帮助**为准。当前开源 **0.3.x**（含 skills 包预置 CLI）**不含**该原生子命令；若 `--help` 提示 unknown command，说明本机 CLI 无盘内上传能力，不要按版本号臆测，也不要用它插智能文档图片（插图走下方「上传附件」）。

**覆盖 / 先删后传时的常见报错**：若 **`drive file delete` 为 403** 且响应里 **`scopeReq` / `insufficient scope` 指向 `app:kso.appfile.readwrite`**，说明网关在该接口上要求 **应用 token** 携带应用侧文件写权限：在开发者控制台为应用开通相应 scope 后，对相关命令使用 **`--token-type app`**（与用户 delegated 上的 `kso.file.readwrite` 是否齐全不是同一件事）。若 **`parse request_upload response`**（简单上传解析失败），多为网关返回的 JSON 形态与 CLI 预期不一致，**升级 CLI** 到已支持宽松解析的版本后再试。

### 上传附件（用于 airpage / airsheet 内嵌图片）

| 场景 | 路径 | 结果 |
|------|------|------|
| 普通文件进云盘目录 | `drive file upload`（需 CLI 已实现该子命令） | 盘内 `file_id` |
| 文档内嵌图 / picture 块 | **附件三步 API**（下） | `attachment_id` |

二者**不是**同一条链路。往智能文档插本地图必须拿到 `attachment_id`，再走 airpage picture 块（见 [wps365-airpage](../wps365-airpage/SKILL.md)）。

`POST /v7/coop/airpage/{file_id}/attachments/upload` **只接受 `file_url`**（从 URL 导入），**不支持本地文件**。本地文件用：

```text
POST /v7/coop/files/{file_id}/attachments/upload/address
→ curl PUT（捕获 ETag / save-key）
→ POST .../attachments/upload/complete
→ data.attachment_id
```

需要 scope：`kso.coop_files.readwrite`。`{file_id}` 是目标智能文档/智能表格的文件 ID。

```bash
# 1) address
wps365-cli api post /v7/coop/files/<FILE_ID>/attachments/upload/address \
  --data '{"name":"pic.png","size":12345,"content_type":"image/png","md5":"<md5>"}'

# 2) PUT：用返回的 request.url + request.headers；-D 保存响应头取 ETag、save-key
curl -sS -D headers.txt -X PUT -H "host:..." -H "x-domain-id:..." \
  --data-binary @local.png "<url>"

# 3) complete → attachment_id
wps365-cli api post /v7/coop/files/<FILE_ID>/attachments/upload/complete \
  --data '{"upload_id":"<UPLOAD_ID>","params":{"etag":"<ETag>","key":"<save-key>"}}'
```

完整插图（含 picture block JSON）见 airpage skill「插入本地图片」节。
## 更多操作

```bash
wps365-cli drive --help
wps365-cli drive file --help
```

### 文件操作

- `drive file list` / `drive file get` — 查询
- `drive file create` — 创建文件或文件夹
- `drive file delete` / `drive file rename` — 删除、重命名
- `drive file batch-copy` / `drive file batch-move`
- `drive file download` — 下载文件
- `drive file upload` — 本地文件上传到父目录（原生子命令）
- `drive file-content get` — 文档内容抽取
- `drive file-path get` — 获取文件路径
- `drive file search` — 搜索文件
- `drive recent-file list` / `drive starred-file list` / `drive frequent-file list` — 最近/收藏/常用

### 权限管理

- `drive link open` / `drive link close` — 开启/关闭分享链接

### 版本管理

- `drive file-version list` / `drive file-version get`

### 盘管理

- `drive list` / `drive get` / `drive create`
- `drive doclib list` / `drive doclib get` — 文档库/团队文档（列文件再走 `drive file list`）

> [!CAUTION]
> 创建、删除、上传文件是**写操作** — 执行前请先与用户确认。

## 另请参阅

- [wps365-getting-started](../wps365-getting-started/SKILL.md) — 接入、`--device --scopes`、权益 FAQ
- [wps365-shared](../wps365-shared/SKILL.md) — 全局参数与认证
- [wps365-airpage](../wps365-airpage/SKILL.md) — 智能文档
- [wps365-airsheet](../wps365-airsheet/SKILL.md) — 智能表格
