---
name: wps365-contacts
description: "WPS 365 通讯录：按关键字搜索企业用户、获取当前用户信息、按用户查询所属部门。当需要查找同事 open_id、查看当前用户身份时触发。禁止用 dept list / dept member list 递归拉取全企业组织与成员。"
metadata:
  requires:
    bins: ["wps365-cli"]
---

# 通讯录 (contacts / user)

> **前置条件：** 先阅读 `../wps365-shared/SKILL.md` 了解认证、全局参数和安全规则。

## 授权模型

| 授权类型 | 操作范围 | 登录方式 |
|---------|---------|---------|
| **delegated** | 搜索用户（search）、获取当前用户（me） | `wps365-cli auth login` |
| **delegated / app** | 按关键字搜用户、查指定用户详情 | `wps365-cli auth login --scopes "..."` 或直接执行命令并加 `--token-type app` |
| **app only** | 部分用户目录查询 | 直接执行目标命令并加 `--token-type app` |

### 登录示例

```bash
wps365-cli auth login --scopes "kso.contact.read,kso.user_base.read"
```

## OAuth Scope

| Scope | 授权类型 | 权限 |
|-------|---------|------|
| `kso.contact.read` | delegated / app | 查询通讯录 |
| `kso.contact.readwrite` | delegated / app | 管理通讯录 |
| `kso.user_base.read` | delegated | 查询当前用户基础信息 |

## 核心用法

### 搜索用户（获取 open_id）

很多 API（日历参与者、IM、忙闲查询）需要用户的 `open_id`。通过搜索命令获取：

```bash
wps365-cli user search --keyword "张三" --page-size 20 --status active --search-field user_name
```

> **已知问题：** API 要求 `search_source` 参数，但精装命令尚未支持。若返回 `ParamFormatError`，使用 `api` 兜底：
>
> ```bash
> wps365-cli api get '/v7/users/search?keyword=张三&page_size=20&status=active&search_field=user_name&search_source=company_user'
> ```

返回结构：
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

`items[].id` 即为用户的 **open_id**。

可选过滤参数：

| 参数 | 说明 |
|------|------|
| `--keyword` | 搜索关键字（必填） |
| `--page-size` | 分页大小 |
| `--status` | 用户状态过滤：`active`、`notactive`、`disabled`、`dimission`（可重复） |
| `--search-field` | 搜索字段：`email`、`phone`、`user_name`、`login_name`（可重复） |

### 获取当前用户

```bash
wps365-cli user me
```

返回当前登录用户的基本信息，`data.id` 即为当前用户的 `open_id`。

### 仅获取当前用户 ID

```bash
wps365-cli user my-id
```

## 更多操作

```bash
wps365-cli user --help
```

### 用户管理（允许）

- `user search` — **优先**：按关键字查找同事 open_id
- `user get` — 获取指定用户详情（支持 `--type email/phone/external-id` 批量反查）
- `user dept list <USER_ID>` / `user depts` — 仅查询**某个用户**所属部门（不是组织树）
- `user list` — 用户列表（仅 app 身份；翻页见下方；勿无必要全量拉取）

### 禁止：全量拉取企业组织与成员

以下命令/用法会暴露企业通讯录下**全部部门与成员**等敏感信息，**一律不要执行**（含臆造命令、`--help` 发现后调用、或 `api` 兜底等价调用）：

```bash
# 禁止
wps365-cli dept list <root_id>
wps365-cli dept member list <root_id> --recursive --all
# 以及等价 api，例如递归遍历：
# wps365-cli api get /v7/depts/{root_id}/children
# wps365-cli api get /v7/depts/{root_id}/members  …并递归子部门
```

找人请用 `user search --keyword "..."`；查某人部门用 `user dept list <USER_ID>`。若用户明确要求导出全公司通讯录，先拒绝并说明风险，除非用户提供书面/明确授权且你已再次确认。

### 用户列表分页（按 next_page_token）

通讯录可配置可见性，`--with-total` / `data.total` **不等于**当前身份可见人数，**不能**用来算页数或决定是否继续翻页。必须跟 `next_page_token`：

```bash
wps365-cli user list --status active --page-size 20 --token-type app
# → 累加 data.items；data.next_page_token 非空则继续：

wps365-cli user list --status active --page-size 20 --token-type app \
  --page-token "<上一页的 next_page_token>"
```

- token 非空 → 带 `--page-token` 再请求；为空或缺失 → 结束。
- **禁止**用 total / `--with-total` 控制翻页。
- `user search` 同样按 `next_page_token` 翻页。

## 另请参阅

- [wps365-user](../wps365-user/SKILL.md) — 用户目录完整流程与排错
- [wps365-shared](../wps365-shared/SKILL.md) — 全局参数与认证
