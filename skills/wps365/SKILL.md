---
name: wps365
description: 用于通过 wps365-cli 接入企业 WPS 365，安装或初始化 CLI、查询和管理云文档、读写智能文档和表格，以及操作日历、会议、邮件、消息和通讯录。用户提到企业 WPS 365、wps365-cli 或要求通过该 CLI 操作办公数据时使用；个人金山文档连接器和本地 Office 文件不属于此入口。
---

# WPS 365 官方套件入口

本目录把官方 15 个 Skill 和各平台 CLI 安装包集中保存。Codex 通过一个入口按需读取官方说明，不需要分别激活子目录。

## 读取顺序

- 首次接入、登录或命令不可用时，读取 [快速接入](.official/wps365-getting-started/SKILL.md)。
- 执行业务命令前，读取 [公共规则](.official/wps365-shared/SKILL.md) 和下表中对应业务说明。只加载当前任务所需材料。
- 官方说明中的相对路径以该说明所在目录为基准。`<SKILLS_PKG>` 对应本目录的 `.official/`。

| 任务 | 官方说明 |
| --- | --- |
| 云盘、搜索、文件上传下载 | [云文档](.official/wps365-drive/SKILL.md) |
| 智能文档正文、块、图片 | [智能文档](.official/wps365-airpage/SKILL.md) |
| 智能表格、工作表和选区 | [智能表格](.official/wps365-airsheet/SKILL.md) |
| 多维表记录 | [记录操作](.official/wps365-dbsheet-records/SKILL.md) |
| 多维表结构、字段 | [结构操作](.official/wps365-dbsheet-schema/SKILL.md) |
| 日历查询与管理 | [日历](.official/wps365-calendar/SKILL.md) |
| 新建日程 | [新建日程](.official/wps365-calendar-insert/SKILL.md) |
| 会议 | [会议](.official/wps365-meeting/SKILL.md) |
| 邮件 | [邮箱](.official/wps365-mail-core/SKILL.md) |
| 即时消息 | [消息](.official/wps365-im/SKILL.md) |
| 通讯录搜索 | [通讯录](.official/wps365-contacts/SKILL.md) |
| 当前用户、用户信息 | [用户](.official/wps365-user/SKILL.md) |
| 用户明确要求 MCP 接入 | [MCP 接入](.official/wps365-mcp/SKILL.md) |

## 本地接入约束

- 使用官方包 `.official/bin/` 中匹配平台的 CLI；凭证由 CLI 存在系统安全存储和用户配置目录，不写入本仓库。
- 本包没有 `spec/`，按官方说明使用 `wps365-cli spec update -y` 获取命令定义。
- 官方 Skill 与当前 CLI 帮助有差异时，先核对 `--help`、版本和实际错误，不直接覆盖已有绑定或清理凭证。
- 只读验证仅执行身份查询和用户指定的数据查询；安装不代表获得发送消息、改文档、删除文件或扩大应用权限的授权。
