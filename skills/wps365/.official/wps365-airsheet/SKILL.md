---
name: wps365-airsheet
description: "WPS 365 智能表格（airsheet）：创建 .ksheet、工作表、选区读写与追加行。当用户需要操作智能表格、ksheet、airsheet 单元格时触发。不要与电子表格 sheets / .xlsx 混淆；不使用内部 CLI 的 build_* 转换器。"
metadata:
  requires:
    bins: ["wps365-cli"]
---

# 智能表格 (airsheet)

> **前置条件：** 首次接入先读 `../wps365-getting-started/SKILL.md`；再读 `../wps365-shared/SKILL.md` 了解认证、全局参数和安全规则。
>
> 旧版升级到含 `airsheet` 精装命令的 CLI 后，先执行 `wps365-cli spec update -y`，再跑本域命令。找不到 `airsheet` 时优先刷新 spec，不要用旧缓存 YAML。

airsheet 是 `.ksheet` 智能表格，不是电子表格 `.xlsx`，也不是多维表 `dbsheet`。

## 授权模型

| 授权类型 | 操作范围 | 登录方式 |
|---------|---------|---------|
| **delegated / app** | 创建表格、工作表、选区读写 | `auth login --device --scopes "..."` 或直接执行命令并加 `--token-type app` |

### 登录示例

登录一律用 `--device`，且必须带 `--scopes`（省略会导致 `granted []`）：

```bash
wps365-cli auth login --device --scopes "kso.airsheet.readwrite,kso.drive.readwrite,kso.file.readwrite"
```

## OAuth Scope

| Scope | 权限 |
|-------|------|
| `kso.airsheet.readwrite` | 创建与读写智能表格 |
| `kso.drive.readwrite` | 定位盘与父目录 |
| `kso.file.readwrite` | 创建 `.ksheet` 会走内部 `request_upload`；缺了会 403 / `400000003` |

> `kso.airsheet.readwrite` 需在 WPS365 开发者后台为应用单独开通。`drive list` 等还可能因企业套餐缺 `interface_company_doc` 报 `ErrPrivileges`（需商业高级版及以上）——不是 OAuth scope。详见 `../wps365-shared/SKILL.md`。

## 核心流程

### 创建智能表格

```bash
wps365-cli drive list --allotee-type user
# → data.items[].id 即为 drive_id

wps365-cli airsheet file create \
  --drive-id <DRIVE_ID> --name "项目跟踪表" --parent-id 0
```

### 工作表

```bash
wps365-cli airsheet worksheet list <FILE_ID>
wps365-cli airsheet worksheet create <FILE_ID> \
  --name "Sheet2" --position-body '{"end":true}'
```

`--position-body` 是必填 JSON 对象（`after_sheet_id` / `before_sheet_id` / `end`）。sub-resource 是单数 `worksheet`，不要写成 `worksheets`。

### 选区读写

复杂 JSON 一律用 `--*-body` 传入，不要使用内部 CLI 的 `build_row_values` / `build_formula_cells`。

`data update` 的每项必须用 **`row_from` / `row_to` / `col_from` / `col_to`** 指定范围（与 OpenAPI `airsheet_update_range_data` 一致）。**不要**传 `row` / `col`——会被服务端忽略，内容会全部写到 A1。

```bash
wps365-cli airsheet data get <FILE_ID> <WORKSHEET_ID> \
  --row-from 0 --row-to 10 --col-from 0 --col-to 5

# ✅ 正确：用范围字段定位单元格（单格则 from=to）
wps365-cli airsheet data update <FILE_ID> <WORKSHEET_ID> \
  --range-data-body '[{"row_from":0,"row_to":0,"col_from":0,"col_to":0,"op_type":"cell_operation_type_formula","formula":"任务名称"}]'

# ❌ 错误：row/col 会被忽略，所有值写到 A1
# --range-data-body '[{"row":0,"col":0,"op_type":"cell_operation_type_formula","formula":"任务名称"}]'

wps365-cli airsheet data delete <FILE_ID> <WORKSHEET_ID> \
  --range-data-body '[{"row_from":0,"row_to":1,"col_from":0,"col_to":1}]'

wps365-cli airsheet data find <FILE_ID> <WORKSHEET_ID> \
  --range-body '{"row_from":0,"row_to":10,"col_from":0,"col_to":5}' \
  --filter-body '{"condition":[],"search":[{"col":0,"value":["hello"]}],"duplicates":{"col":[]}}'
```

### 追加行

```bash
wps365-cli airsheet row create <FILE_ID> <WORKSHEET_ID> \
  --range-data-body '[{"op_type":"cell_operation_type_formula","formula":"a"}]'
```

sub-resource 是单数 `row`，不要写成 `rows`。

## 更多操作

```bash
wps365-cli airsheet --help
wps365-cli airsheet data --help
```

条件格式、浮动图片、整表导出/保护等低频能力走 `wps365-cli api`。

> [!CAUTION]
> 更新、删除选区和追加行是**写操作** — 执行前请先与用户确认。

## 另请参阅

- [wps365-getting-started](../wps365-getting-started/SKILL.md) — 接入、`--device --scopes`、权益 FAQ
- [wps365-shared](../wps365-shared/SKILL.md) — 全局参数与认证
- [wps365-drive](../wps365-drive/SKILL.md) — 盘与文件
- [wps365-dbsheet-schema](../wps365-dbsheet-schema/SKILL.md) — 多维表（不要与 airsheet 混淆）
