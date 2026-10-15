---
name: wps365-dbsheet-records
description: "WPS 365 多维表数据操作：records 查询/检索/新增/更新/删除。当用户需要批量处理记录、按条件筛选数据时触发。"
metadata:
  requires:
    bins: ["wps365-cli"]
---

# 多维表数据读写 (dbsheet records)

> **前置条件：** 先阅读 `../wps365-shared/SKILL.md` 了解认证、全局参数和安全规则。

## 授权模型

记录命令在精装规范中为 `auth_mode: both`，支持 delegated / app。

## 命令总览

```bash
wps365-cli dbsheet record --help
```

- `dbsheet record list` / `dbsheet record-page list`：分页读取
- `dbsheet record get` / `search`：单条/批量检索
- `dbsheet record create` / `update` / `delete`：写入与删除

## 推荐流程

### 流程 A：先读再改

```bash
# 1) 先查列表
wps365-cli dbsheet record list <FILE_ID> <SHEET_ID> --page-size 20 --show-fields-info

# 2) 再读单条
wps365-cli dbsheet record get <FILE_ID> <SHEET_ID> <RECORD_ID> --show-record-extra-info
```

### 流程 B：条件查询与页码查询

```bash
# token 分页
wps365-cli dbsheet record list <FILE_ID> <SHEET_ID> \
  --fields "任务名,状态" \
  --page-size 50

# 页码分页
wps365-cli dbsheet record-page list <FILE_ID> <SHEET_ID> \
  --page-num 1 \
  --page-size 20
```

如果有复杂筛选，使用 `--filter-body`（JSON）：

```bash
wps365-cli dbsheet record list <FILE_ID> <SHEET_ID> \
  --filter-body '{"conjunction":"and","conditions":[]}'
```

### 流程 C：创建与更新记录

```bash
# 创建记录
wps365-cli dbsheet record create <FILE_ID> <SHEET_ID> \
  --records-body '[{"fields_value":"{\"任务名\":\"完成设计\",\"状态\":\"进行中\"}"}]'

# 批量更新记录
wps365-cli dbsheet record update <FILE_ID> <SHEET_ID> \
  --records-body '[{"id":"rec_xxx","fields_value":"{\"状态\":\"已完成\"}"}]'
```

说明：
- `--records-body` 是 JSON 数组字符串。
- 更新时每项通常至少包含 `id` 与 `fields_value`。

### 流程 D：批量删除与批量检索

```bash
# 批量检索
wps365-cli dbsheet record search <FILE_ID> <SHEET_ID> \
  --records "rec_001,rec_002"

# 批量删除
wps365-cli dbsheet record delete <FILE_ID> <SHEET_ID> \
  --records "rec_001,rec_002"
```

## 关键参数说明

- `--fields`：逗号分隔字段名列表
- `--records`：逗号分隔记录 ID 列表
- `--show-fields-info`：返回字段 schema，便于动态映射
- `--show-record-extra-info`：返回扩展信息
- `--text-value`：控制文本值格式
- `--prefer-id`：优先按指定 ID 处理

## 实战建议

- 先小批量验证，再大批量更新/删除。
- 记录写入前先读取一次目标记录，避免覆盖错误字段。
- 对复杂 JSON 参数，先本地保存到变量或文件并校验格式。

## 常见排错

| 现象 | 常见原因 | 处理建议 |
|------|----------|----------|
| 参数解析失败 | `records-body/filter-body` 非法 JSON | 用 `jq .` 校验后再传 |
| 更新无效果 | `id` 错误或字段键不匹配 | 先 `records get` 确认记录 ID 和字段名 |

## 安全提示

- `records update/delete` 是写操作，执行前确认影响范围。
- 批量删除建议先 `records search` 做预览清单再执行删除。

## 另请参阅

- [wps365-shared](../wps365-shared/SKILL.md) — 全局参数、认证与调试
- [wps365-dbsheet-schema](../wps365-dbsheet-schema/SKILL.md) — 表结构、字段、视图治理
