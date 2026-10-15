# WPS 365 官方套件

来源为 WPS 使用指南提供的 v0.3.6 压缩包。`.official/` 保持上游文件原样，包含 15 个 Skill、1 份英文接入说明、MCP 配置样例和 6 个平台的 CLI 安装包。`upstream.json` 记录来源、压缩包校验值及每个原始文件的 SHA-256。

`SKILL.md` 是本仓库添加的唯一激活入口。Agent Manager 可将整个 `skills/wps365/` 链接到 Codex；不单独链接 15 个官方子目录。


## 如何调用

自然语言可以使用“金山协作、WPS 协作、协作云文档、企业金山文档、WOA、WPS365”等叫法，例如“列一下协作上最近打开的文档”“在金山协作里搜索项目周报”“查今天协作里的日程”。已经确认企业 WPS 上下文后，可以接着说“刚才那个文档”“我的表格”，不必重复产品名。

也可以显式使用 `$wps365`，例如“用 $wps365 列出我最近访问的文档”。普通团队协作讨论、个人金山文档连接器、本地 Office 排版或 WPS 桌面故障不走这个入口；没有平台线索的“云文档、金山文档”先辨明账号类型。别名与用法写在根 `SKILL.md`，官方 `.official/` 内容不作修改，后续上游同步会保留这些本地说明。

自动选择由模型判断，别名和示例用于减少漏选，不能保证所有表达都命中；显式点名 `$wps365` 可以明确指定本入口。`evals/trigger-evals.json` 保存 26 个独立场景，包含 16 个应触发、8 个不触发、2 个需要澄清的场景。一次独立的元数据路由评估中，正例命中从 4/16 提升到 16/16，反例排除 8/8，歧义澄清 2/2；这是离线样例结果，不是所有真实表达的命中率。

## 安装与验证

先阅读 `.official/wps365-getting-started/SKILL.md`。Apple 芯片 Mac 的 CLI 位于 `.official/bin/wps365-cli-aarch64-apple-darwin.tar.gz`；安装到用户 `~/.local/bin/` 后，执行：

```bash
wps365-cli --version
wps365-cli spec update -y
wps365-cli config init
wps365-cli auth login --device --scopes "kso.user_base.read"
wps365-cli user me
```

CLI 会提供浏览器登录和授权入口；设备码登录进程需要保持运行直到成功。进一步查询云文档前，应按业务说明核对实际需要的权限和企业套餐。

## 更新

发布包来源已配置在 `tools/upstream_sync/upstream.yml` 的 `wps365` 条目。现有每周自动检查也会检查 WPS 的官方版本索引；有新版时下载对应 Skill ZIP，并在更新 PR 中呈现差异。

```bash
uv run upstream-sync check
uv run upstream-sync diff
uv run upstream-sync sync --upstream wps365
```

同步仅写 `.official/` 和 `upstream.json`，保留本地 `SKILL.md`。锁文件记录版本与压缩包 SHA-256，来源记录同时保存逐文件校验值。上游删除的文件保留并打印警告，需人工处理；同版本不重复下载。发布包缺失、下载或校验失败时不会推进锁文件。不要把账号、密钥、token 或运行输出加入本目录。

本机 CLI 是独立安装的副本，同步仓库不会自动替换正在使用的可执行文件；升级时按官方接入说明安装对应平台版本并验证。

官方目录使用 `.official/`，避免 Codex 的递归发现把 15 个参考入口再次列成独立 Skill；相对路径和文件内容保持上游原样。
