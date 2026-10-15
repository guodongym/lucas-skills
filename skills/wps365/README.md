# WPS 365 官方套件

来源为 WPS 使用指南提供的 v0.3.6 压缩包。`.official/` 保持上游文件原样，包含 15 个 Skill、1 份英文接入说明、MCP 配置样例和 6 个平台的 CLI 安装包。`upstream.json` 记录来源、压缩包校验值及每个原始文件的 SHA-256。

`SKILL.md` 是本仓库添加的唯一激活入口。Agent Manager 可将整个 `skills/wps365/` 链接到 Codex；不单独链接 15 个官方子目录。

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
