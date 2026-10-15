---
name: wps365-user
description: "WPS 365 用户目录：搜索用户、当前身份、批量反查、查询指定用户所属部门。当需要查找同事 open_id、查看当前用户身份时触发。禁止 dept list / dept member list --recursive --all 全量拉取企业组织与成员。"
metadata:
  requires:
    bins: ["wps365-cli"]
---

# 用户目录 (user)

> **前置条件：** 先阅读 `../wps365-shared/SKILL.md` 了解认证、全局参数和安全规则。

## 授权模型

- `user me`：当前登录用户身份（delegated）
- `user list/get/search`：用户目录查询（delegated / app）
- `user get --type email/phone/external-id`：批量反查（delegated / app）
- `user dept list`：用户所属部门查询（app）

如遇 `--token-type=delegated is incompatible with operation security`，改用 app 身份。

## 命令总览

```bash
wps365-cli user --help
```

- `user me` — 获取当前用户信息
- `user get` — 获取指定用户详情
- `user list` — 列出企业用户
- `user search` — 搜索企业用户
- `user dept list` — 查询用户所在部门

## 标准操作流程

### 流程 A：获取当前身份

```bash
wps365-cli user me --token-type delegated
```

返回当前登录用户的基本信息，`data.id` 即为当前用户的 `open_id`。

### 流程 B：搜索用户（获取 open_id）

很多 API（日历参与者、IM、忙闲查询）需要用户的 `open_id`。通过搜索命令获取：

```bash
wps365-cli user search --keyword "张三"
```

默认按 `user_name` 字段搜索企业内（`company_user`）的活跃（`active`）用户。

搜索参数：

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `--keyword` | 搜索关键字（必填） | — |
| `--page-size` | 分页大小 | API 默认 20 |
| `--status` | 用户状态：`active`、`notactive`、`disabled`、`dimission`（可重复） | `active` |
| `--search-field` | 搜索字段：`email`、`phone`、`user_name`、`login_name`（可重复） | `user_name` |
| `--search-source` | 搜索来源：`company_user`、`enterprise_partner`（可重复） | `company_user` |
| `--search-source-v2` | 搜索来源 v2：`company_user`、`enterprise_partner`（可重复） | — |
| `--user-type` | 用户类型：`company_member`、`external_guest`（可重复） | — |
| `--page-token` | 分页标记（取响应 `data.next_page_token`） | — |
| `--with-total` | 是否返回总数（**不可靠，勿用来控制翻页**） | — |

返回结构中 `items[].id` 即为用户的 **open_id**：
```json
{
  "code": 0,
  "data": {
    "items": [
      {
        "id": "6nwx8dD",
        "user_name": "张三",
        "def_dept_name": "应用中台研发组",
        "status": "active"
      }
    ]
  }
}
```

搜索后拉取详情和部门：

```bash
wps365-cli user get <USER_ID> --with-dept
wps365-cli user dept list <USER_ID>
```

### 流程 C：批量反查

```bash
wps365-cli user get "a@example.com,b@example.com" --type email --status active
wps365-cli user get "13800138000,13900139000" --type phone --status active
wps365-cli user get "ext1,ext2" --type external-id --status active
```

### 流程 D：分页浏览用户列表（按 next_page_token）

通讯录可配置可见性，`--with-total` / 响应里的 `total` **不等于**当前身份可见的人数，**不能**用 total 算页数或决定是否继续翻页。正确做法是跟 `next_page_token`：

```bash
# 第一页
wps365-cli user list --status active --page-size 20
# → 读取 data.items；若 data.next_page_token 非空则继续

# 下一页：把上一页的 next_page_token 原样传入 --page-token
wps365-cli user list --status active --page-size 20 --page-token "<上一页的 next_page_token>"
```

**Agent 翻页规则：**

1. 每页取 `data.items` 累加；以 `data.next_page_token` 是否非空判断是否还有下一页。
2. token 非空 → 带 `--page-token` 再请求；为空或缺失 → 结束。
3. **禁止**用 `--with-total`、`data.total` 或「已拉条数 vs total」决定是否继续。
4. `user search` 同样用 `next_page_token` / `--page-token`，不要依赖 total。

## 参数与约束

- `status` 常用值：`active`、`notactive`、`disabled`（`search` 还支持 `dimission`）
- `id-type` 会映射到请求头 `X-Kso-Id-Type`，仅在多 ID 体系时使用
- `user list` 仅支持应用身份（`--token-type app` 或默认 app）

## 常见排错

| 现象 | 常见原因 | 处理建议 |
|------|----------|----------|
| incompatible with operation security | 用了 delegated 调 app-only 接口 | 改用 app 身份或不强制 token-type |
| 参数校验失败 | `user-ids/dept-ids` 格式错误 | 使用英文逗号分隔，避免空项 |
| 查询结果为空 | 过滤条件过严或身份/可见范围不足 | 放宽过滤；检查通讯录可见性与 token 身份 |
| total 与实际可见人数不一致 | 通讯录可见性导致 total 不准确 | 忽略 total，按 `next_page_token` 翻页 |

## 安全提示

- `user me` / `user list` 等返回包含个人信息，输出到日志前先确认脱敏策略。
- **禁止**执行会拉取全企业组织/成员的命令，例如：
  - `wps365-cli dept list <root_id>`
  - `wps365-cli dept member list <root_id> --recursive --all`
  - 以及 `api get /v7/depts/{id}/children` / `.../members` 的递归全量遍历
- `user dept list <USER_ID>` 仅用于查询**单个用户**所属部门，不是组织树枚举；找人用 `user search`。

## 另请参阅

- [wps365-shared](../wps365-shared/SKILL.md) — 全局参数、认证与调试
