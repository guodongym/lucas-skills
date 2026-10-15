---
name: wps365-airpage
description: "WPS 365 智能文档（airpage）：创建/读取、v2 块读写（写正文只用 block create --content 或 v2 api 内层 JSON）、禁止 v1 --arg 与用 import 写正文、本地图片经 coop 附件三步上传后插 picture 块、OTL JSON 导入与导出。当用户需要操作智能文档、.otl、airpage 块、往智能文档写文字或插本地图片时触发。不负责 Markdown 一键写回。"
metadata:
  requires:
    bins: ["wps365-cli"]
---

# 智能文档 (airpage)

> **前置条件：** 首次接入先读 `../wps365-getting-started/SKILL.md`；再读 `../wps365-shared/SKILL.md` 了解认证、全局参数和安全规则。
>
> 旧版升级到含 `airpage` 精装命令的 CLI 后，先刷新本地 spec（优先覆盖 skills 包 `spec/`，见 shared），再跑本域命令。找不到 `airpage` 时优先刷新 spec，不要用旧缓存 YAML。

## 授权模型

| 授权类型 | 操作范围 | 登录方式 |
|---------|---------|---------|
| **delegated / app** | 创建、读取、块读写、导入导出、附件上传 | `auth login --device --scopes "..."` 或直接执行命令并加 `--token-type app` |

### 登录示例

登录一律用 `--device`，且必须带 `--scopes`（省略会导致 `granted []`）：

```bash
wps365-cli auth login --device --scopes "kso.airpage.readwrite,kso.drive.readwrite,kso.file.readwrite,kso.coop_files.readwrite"
```

插本地图片还需要 **`kso.coop_files.readwrite`**（`/v7/coop/files/.../attachments/upload*`）。

## OAuth Scope

| Scope | 权限 |
|-------|------|
| `kso.airpage.readwrite` | 创建与读写智能文档 |
| `kso.drive.readwrite` | 定位盘与父目录（创建时需要 `drive_id`） |
| `kso.file.readwrite` | 创建 `.otl` 会走内部 `request_upload`；缺了会 403 / `400000003` |
| `kso.coop_files.readwrite` | 文档内附件三步上传（本地图片 → `attachment_id`） |

> `kso.airpage.readwrite` 需在 WPS365 开发者后台为应用单独开通。`drive list` 等还可能因企业套餐缺 `interface_company_doc` 报 `ErrPrivileges`（需商业高级版及以上）——不是 OAuth scope。详见 `../wps365-shared/SKILL.md`。

## 写入正文：正确路径与 Agent 禁令（先读）

往智能文档**写一段字 / 插块**时，优先精装 v2；失败多半是走错命令或 body 多包了一层 `request`，**不要改 CLI 通用策略**，按本表改调用方式。

| 目标 | 正确做法 | 禁止 / 易失败 |
|------|----------|----------------|
| 写纯文本段落 | `airpage block create <FILE_ID> --content "..."` | ~~`airpage import create`~~（那是 OTL 导入，不是写正文） |
| 读块树 | `airpage block get <FILE_ID>` | ~~`api .../blocks/batch_get` 且 body 包 `request`~~ → 报 `block_ids` 为空 |
| heading / picture / 列表等 | `api post /v7/airpage/v2/<FILE_ID>/blocks/create --data '{内层 JSON}'` | ~~v1 `airpage block create --arg`~~；~~`--data '{"request":{...}}'`~~ |
| 已有 OTL JSON 字符串导入 | `airpage import create --content '<OTL 字符串>'` | 把普通段落 JSON / Markdown 塞进 `--content` 当写正文 |

**硬性禁令：**

1. **禁止** `airpage block create --arg`（及任何 v1 opaque `arg`）。开源侧无法编码 protobuf bytes；写正文**只用** v2 `--content` 或下方 v2 `api post`。
2. **禁止**用 `airpage import create` 写正文。`import` 只接受**已有 OTL JSON 字符串**；误传对象/段落 JSON 可能退出码 0 但文档不变。
3. **禁止**给 v2 块接口的 `--data` 再包一层 `{"request":{...}}`。网关要的是**内层**，例如 create 直接 `{"block_id":"doc","doc_children":{...}}`；batch_get 直接 `{"block_ids":["doc"]}`。
4. `api --data` **原样透传**，不会把 path 里的 `file_id` 注入 body，也不会自动拆 `request` / 改 camelCase。path 用 **`/v7/airpage/v2/...`**，不要混用错误版本路径。

查块优先：

```bash
wps365-cli airpage block get <FILE_ID>
# 若坚持用 api（少用）：
wps365-cli api post /v7/airpage/v2/<FILE_ID>/blocks/batch_get \
  --data '{"block_ids":["doc"]}'
```

## 核心流程

### 创建智能文档

```bash
wps365-cli drive list --allotee-type user
# → data.items[].id 即为 drive_id

wps365-cli airpage create \
  --drive-id <DRIVE_ID> --parent-id 0 --name "会议纪要" \
  --template-id "" --on-name-conflict rename
```

`--template-id ""` 表示空白文档。这不是 Markdown 写回。

### 读取基本信息

```bash
wps365-cli airpage get <FILE_ID>
```

### 块读写（v2 JSON）

块命令绑定 v2 `POST /v7/airpage/v2/{file_id}/blocks*`。`airpage block create --content` **只适合插入纯文本段落**。标题、图片、有序/无序列表等请用 `api post` + 下方 JSON 示例。

```bash
# ✅ 写正文主路径（纯文本段落）
wps365-cli airpage block create <FILE_ID> --content "test测试123"
wps365-cli airpage block get <FILE_ID>
wps365-cli airpage block update <FILE_ID> --block-id <BLOCK_ID> --content "更新后的文本"
wps365-cli airpage block delete <FILE_ID> --start-index 0 --end-index 1
```

`--block-id` 在 get/create/delete 默认 `doc`（文档根）。update 必须传段落块 ID，可从 `airpage block get` 的块树里取。

**不要**使用 `airpage block create --arg`（v1）。复杂块用 `api post` 时 JSON **不要**包 `request`，直接发内层，例如 `{"block_id":"doc","doc_children":{...}}`。

### 块类型与写法对照

| 块类型 | `--content` 适用 | 写法 |
|--------|------------------|------|
| paragraph（纯文本） | ✅ | `airpage block create --content "..."` |
| heading | ❌ | `api post`，见下方 heading 示例 |
| picture | ❌ | 先附件上传拿 `attachment_id`，再 `api post` picture |
| number_list（有序列表） | ❌ | 实际是 **paragraph + `attributes.ordered`**，见下方示例 |
| bullet_list（无序列表） | ❌ | paragraph + `attributes.bullet` |

#### heading（标题）

```bash
wps365-cli api post /v7/airpage/v2/<FILE_ID>/blocks/create --data '{
  "block_id": "doc",
  "doc_children": {
    "children": [{
      "heading": {
        "attributes": { "level": 1 },
        "elements": [{
          "text": {
            "attributes": { "content": "一、会议纪要" },
            "range_marks": []
          }
        }],
        "range_marks": []
      }
    }]
  }
}'
```

`level` 为 1–6（H1–H6）。

#### picture（图片块）

`attributes.id` = 附件上传返回的 `attachment_id`；`width` / `height` 为原始像素，须 > 0。

```bash
wps365-cli api post /v7/airpage/v2/<FILE_ID>/blocks/create --data '{
  "block_id": "doc",
  "doc_children": {
    "children": [{
      "picture": {
        "attributes": {
          "id": "<ATTACHMENT_ID>",
          "width": 800,
          "height": 600
        },
        "range_marks": []
      }
    }]
  }
}'
```

#### number_list（有序列表项）

OpenAPI **没有**独立 `number_list` 块；用 paragraph 带 `ordered`：

```bash
wps365-cli api post /v7/airpage/v2/<FILE_ID>/blocks/create --data '{
  "block_id": "doc",
  "doc_children": {
    "children": [{
      "paragraph": {
        "attributes": {
          "ordered": {
            "style": "arabic_num",
            "format": "dot_suffix",
            "level": 0,
            "id": "list1"
          }
        },
        "elements": [{
          "text": {
            "attributes": { "content": "第一项" },
            "range_marks": []
          }
        }],
        "range_marks": []
      }
    }]
  }
}'
```

同一组有序列表多项应共享相同的 `ordered.id`，以保持连续编号。无序列表把 `ordered` 换成 `"bullet": {"style": "dot", "level": 0}`。

### 插入本地图片（三步附件上传 + picture block）

精装命令**没有**本地插图一键命令。本地文件走 **coop 附件三步**拿 `attachment_id`，再创建 picture 块。附件流程细节也可对照 [wps365-drive](../wps365-drive/SKILL.md)「上传附件」节。

> **不要**用 `POST /v7/coop/airpage/{file_id}/attachments/upload` 传本地文件——该接口只接受可访问的 **`file_url`**（远程 URL 导入）。  
> **不要**用 `drive file upload`——那是盘内普通文件，拿不到 picture 块要的 `attachment_id`。

`<FILE_ID>` 是智能文档本身的 file id（`airpage create` / `airpage get` 返回的那个）。

```bash
FILE_ID="<FILE_ID>"
LOCAL="/path/to/pic.png"
NAME="$(basename "$LOCAL")"
SIZE=$(wc -c < "$LOCAL" | tr -d ' ')
# macOS: md5 -q；Linux: md5sum | awk '{print $1}'
MD5=$(md5 -q "$LOCAL" 2>/dev/null || md5sum "$LOCAL" | awk '{print $1}')
CT="image/png"   # 按实际：image/jpeg、image/webp 等
```

**1. 获取上传地址**

```bash
wps365-cli api post "/v7/coop/files/${FILE_ID}/attachments/upload/address" \
  --data "{\"name\":\"${NAME}\",\"size\":${SIZE},\"content_type\":\"${CT}\",\"md5\":\"${MD5}\"}" \
  -o json
# → data.upload_id
# → data.request.url / data.request.method / data.request.headers（PUT 时原样带上）
# → data.send_back_params 含 key 等回填字段（complete 时与 PUT 响应头对齐）
```

**2. PUT 到对象存储（必须捕获响应头）**

把 `data.request.headers` 里的键值全部加到 curl（常见 `host`、`x-domain-id`、`Content-Type` 等），并保存响应头：

```bash
# 将 address 返回的 headers 展开为 -H；URL 用 data.request.url
curl -sS -D /tmp/att-headers.txt -o /tmp/att-body.bin -X PUT \
  -H "host: <from address>" \
  -H "x-domain-id: <from address>" \
  --data-binary @"${LOCAL}" \
  "<data.request.url>"
```

从响应头取 **ETag**（去引号）与 **save-key**（或与 `send_back_params.key` 一致的 key 字段；以实际响应头名为准）。缺 ETag/key 则 complete 会失败。

**3. 完成上传 → `attachment_id`**

```bash
wps365-cli api post "/v7/coop/files/${FILE_ID}/attachments/upload/complete" \
  --data "{\"upload_id\":\"<UPLOAD_ID>\",\"params\":{\"etag\":\"<ETag>\",\"key\":\"<save-key或send_back_params.key>\"}}" \
  -o json
# → data.attachment_id
```

**4. 创建 picture block**

用上节 picture JSON，把 `id` 换成 `data.attachment_id`；`width`/`height` 用图片真实像素（可用 `sips -g pixelWidth -g pixelHeight` / `identify` 等读取）。

**从 URL 导入附件（非本地文件）** 才用：

```bash
wps365-cli api post /v7/coop/airpage/<FILE_ID>/attachments/upload \
  --data '{"attachment_name":"pic.png","file_url":"https://example.com/pic.png"}'
```

### 导入 OTL JSON（不是写正文、不是 Markdown）

`airpage import create --content` **只用于导入已有 OTL JSON 字符串**，不是往文档写普通段落的入口。写正文请用上一节的 `block create --content` / v2 `api post`。

```bash
# ✅ 仅当手头已是合法 OTL 内容字符串时
wps365-cli airpage import create <FILE_ID> --content '<已有-OTL-JSON-字符串>'
```

常见误用（会导致「命令成功但文档没变」或格式错误）：

- 把段落 / heading 的块 JSON、或 Markdown 塞进 `--content` 当写正文
- 把 JSON **对象**当参数再指望 CLI「自动 stringify 成 OTL」（开源 CLI 不会做这层转换）

从 docx 导入请用 `api`：`POST /v7/airpage/import_from_docx/async_tasks/create`。

### 导出

```bash
wps365-cli airpage export create <FILE_ID> --format docx
wps365-cli airpage export create <FILE_ID> --format json
wps365-cli airpage export get <FILE_ID> --format docx --version "1" --task-id <TASK_ID>
```

pdf 请求体字段很多，精装不绑完整 body，请用：

```bash
wps365-cli api post /v7/airpage/<FILE_ID>/export_to_pdf --data '{...}'
```

不要使用未落地的历史命令名 `doc airpage export-*`。

## 更多操作

```bash
wps365-cli airpage --help
wps365-cli airpage block --help
wps365-cli airpage export --help
```

## 常见失败对照（写入）

| 现象 | 根因 | Agent 怎么改 |
|------|------|----------------|
| `import create` 退出 0 但正文不变 | 把写正文当成了 OTL 导入；或 content 不是合法 OTL | 改用 `block create --content`；import 仅保留给现成 OTL |
| 仍在用 `--arg` / 找不到可编码的 arg | v1 arg 是 protobuf bytes，开源不做编解码 | 删掉 `--arg`，改 v2 `--content` 或下方 JSON |
| `api .../blocks/create` 失败或字段无效 | `--data` 多包了 `{"request":{...}}` | 只发内层；path 用 `/v7/airpage/v2/.../blocks/create` |
| `batch_get` 报 `block_ids` 为空 | 同上，`block_ids` 落在被忽略的 `request` 里 | 优先 `airpage block get`；api 则 `--data '{"block_ids":["doc"]}'` |
| 抱怨 path/body `file_id` 冲突或数组被包坏 | `api` 不会自动注入 path 参数到 body | 自己在 `--data` 里写齐字段；不要臆造全局 camelCase / 拆 request |

> [!CAUTION]
> 创建、更新、删除块与附件上传是**写操作** — 执行前请先与用户确认。

## 另请参阅

- [wps365-getting-started](../wps365-getting-started/SKILL.md) — 接入、`--device --scopes`、权益 FAQ
- [wps365-shared](../wps365-shared/SKILL.md) — 全局参数与认证、升级覆盖 spec
- [wps365-drive](../wps365-drive/SKILL.md) — 盘与文件、文档库、**附件上传 vs 盘上传**
