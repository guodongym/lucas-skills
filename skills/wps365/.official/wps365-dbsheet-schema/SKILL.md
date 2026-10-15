---
name: wps365-dbsheet-schema
description: "WPS 365 多维表结构治理：schema、sheets、fields 的建模与维护。当用户需要新建/改造多维表结构时触发。"
metadata:
  requires:
    bins: ["wps365-cli"]
---

# 多维表结构治理 (dbsheet schema)

> **前置条件：** 先阅读 `../wps365-shared/SKILL.md` 了解认证、全局参数和安全规则。

## 授权模型

`dbsheet` 结构类命令在精装规范中均为 `auth_mode: both`，支持 delegated / app。

```bash
# 查看当前认证状态
wps365-cli auth status
```

## 命令总览

```bash
wps365-cli dbsheet --help
wps365-cli dbsheet schema --help
wps365-cli dbsheet sheet --help
wps365-cli dbsheet field --help
```

- `dbsheet schema get`：读取完整结构
- `dbsheet sheet create/update/delete`：数据表生命周期
- `dbsheet field create/update/delete`：字段治理

## 推荐流程

### 流程 A：建模前先读 schema

```bash
wps365-cli dbsheet schema get <FILE_ID> -o json
```

先确认这些对象 ID，再做变更：
- `sheet_id`
- `field_id`

### 流程 B：创建新数据表（含初始字段和视图）

```bash
wps365-cli dbsheet sheet create <FILE_ID> \
  --name "任务跟踪" \
  --fields-body '[{"name":"任务名","type":"MultiLineText"},{"name":"状态","type":"SingleSelect"}]' \
  --views-body '[{"name":"默认视图","type":"Grid"}]'
```

说明：
- `--fields-body`、`--views-body` 都是 JSON 数组字符串。
- 字段类型按 PascalCase（如 `MultiLineText`、`SingleSelect`）。

### 流程 C：字段变更

```bash
# 新增字段
wps365-cli dbsheet field create <FILE_ID> <SHEET_ID> \
  --fields-body '[{"name":"优先级","type":"SingleSelect"}]'

# 更新字段（如重命名）
wps365-cli dbsheet field update <FILE_ID> <SHEET_ID> \
  --fields-body '[{"id":"fld_xxx","name":"优先级(新版)"}]'

# 删除字段（可批量）
wps365-cli dbsheet field delete <FILE_ID> <SHEET_ID> \
  --fields "fld_xxx,fld_yyy"
```

## 关键参数与易错点

- `sheets create`：
  - `--fields-body` 必填
  - `--views-body` 必填
  - `--after-sheet-id` 与 `--before-sheet-id` 用于插入位置
- `fields delete --fields`：逗号分隔，支持批量

## 安全与变更策略

- 结构变更（删字段/删表）影响大，必须先确认业务影响面。
- 建议顺序：`schema get` 盘点 -> 小范围试改 -> 再批量执行。
- 对 JSON 参数不确定时先 `--dry-run` 预览请求。

## 常见排错

| 现象 | 常见原因 | 处理建议 |
|------|----------|----------|
| JSON 解析错误 | `--fields-body/--views-body` 格式非法 | 先用 `jq` 验证 JSON，再执行 |
| 找不到对象 ID | 使用了旧 ID 或跨文件 ID | 重新执行 `dbsheet schema get` 获取最新 ID |
| 权限不足 | token 身份或 scope 不匹配 | `auth status` 检查身份并补授权 |

## 另请参阅

- [wps365-shared](../wps365-shared/SKILL.md) — 全局参数、认证与调试
- [wps365-dbsheet-records](../wps365-dbsheet-records/SKILL.md) — 记录读写
