# 命令与环境

本目录 `scripts/ezone.py` 是 CLI 唯一入口，源码版本由 `--version` 回读；来源是 lucas-skills 的 `skills/ezone/scripts/`，随整个目录共同升级，不依赖 `.git`。只复制 `SKILL.md` 不包含 CLI。

## 首次使用

准备 Python 3.11+；本地提交、推送另需 Git。取得完整 Skill 目录后，在目标项目内配置入口；下面替换为实际绝对目录，项目内安装时通常为 `<project>/.agents/skills/ezone`。后续 `ez` 均指此函数，无需安装全局 CLI 或运行 `uv sync`：

```sh
ezone_skill='/absolute/path/to/ezone'
ez() { python3 "$ezone_skill/scripts/ezone.py" --json "$@"; }
```

项目维护者将 [配置样例](../assets/ezone.example.json) 复制到项目根目录 `.ezone.json`，填写所在实例的 HTTPS 地址、认证查询确认的仓库标识 `repoKey` 和企业标识。`repo` 是字符串，不是 Git remote、仓库名或路径。该文件只保存以下非机密字段，可随项目提交：

```json
{
  "host": "https://ezone.example.com",
  "repo": "REPLACE_WITH_REPO_KEY",
  "company": "REPLACE_WITH_COMPANY"
}
```

只有已安装的 Skill 而不知道 repoKey 时，可先只填写 `host` 和已知的 `company`，登录后用 `ez repo list --paginate` 查询；再由项目维护者补全 `repo`。`company` 对流水线／制品请求必需。非空值与类型会被校验；项目配置不接受 `token` 或其他字段。

每位使用者自行从所在 Ezone 平台取得个人访问令牌，权限须覆盖自己要执行的操作；不共用维护者的账号或令牌。然后在自己的交互终端运行：

```sh
ez auth login
ez doctor
ez auth status
```

`auth login` 隐藏输入令牌，仅执行一次仓库列表只读探测，成功后才保存到 `~/.config/ezone/credentials.json`；认证失败或写盘失败保留旧凭据。无法隐藏输入或输入中断时停止，不退化成明文输入。不自动申请令牌、扩大权限或读取浏览器 Cookie。不要把真实令牌粘进聊天、命令参数、URL、仓库或日志。

个人凭据按规范化 HTTPS origin 精确匹配：同平台多个项目共用一份个人配置，不同域名／非默认端口隔离；每个平台当前只保存一个账号的令牌。macOS/Linux 新建凭据目录为 `700`、文件为 `600`，采用同目录原子替换。文件是本机明文，不能公开分享；已有文件为软链、JSON 损坏或权限过宽时拒绝使用和覆盖，先自行修复或移走原文件。Windows 使用用户 HOME 下同一路径，访问控制由操作系统管理。

从项目的任意子目录调用时，CLI 向上读取最近的 `.ezone.json`，到最近 `.git` 目录或 worktree 的 `.git` 文件为止；无 Git 边界时只检查当前目录。不读取 Skill 源目录的项目配置，也不自动读取项目 `.env`。从项目外调用需显式传参或环境配置。

## 配置优先级与诊断

主机、仓库、企业依次取：全局参数 `--host`／`--repo`／`--company` > 非空 `EZONE_HOST`／`EZONE_REPO`／`EZONE_COMPANY` > 项目文件。令牌依次取：非空 `EZONE_TOKEN` > 与当前平台匹配的个人凭据。环境变量供临时覆盖与 CI 使用，不要求写进 shell 启动文件。使用环境令牌时，必须同时用受信任的 `EZONE_HOST` 或显式 `--host` 确定目标；仅靠项目文件的 `host` 会在请求前被拒绝，避免切换项目时将原平台令牌发往另一平台。显式参数优先于环境，调用前用 `doctor` 核对实际目标。

CI 从平台机密变量注入 `EZONE_TOKEN`，并在可信 CI 配置中同时设置非机密的 `EZONE_HOST`；不要运行交互式 `auth login`。仓库与企业仍可从 `.ezone.json` 读取。Skill 和同步版本清单不携带凭据。项目内的 Skill 固定版本并随代码提交，选择多个 Skill、来源清单和更新规则由消费项目维护；公开源仓库只维护 Skill 与发布产物。

```sh
ez repo list --paginate
ez repo view
ez branch list --paginate
ez repo rules
```

直接调用也可：`python3 /absolute/path/to/ezone/scripts/ezone.py --host https://ezone.example.com --repo REPO_KEY --company COMPANY --json pr view 2`。所有全局选项放资源名前。`--help`、`--version`、`doctor` 不触网；doctor 显示非机密的主机／仓库／企业及配置路径，只显示令牌是否存在和来源 `environment`／`credentials`／`none`，不显示令牌值。输出总为 JSON，`--json` 保留为显式调用约定，诊断在标准错误。

网络须能访问目标 HTTPS 且证书可信；可使用环境支持的 `HTTPS_PROXY`、`SSL_CERT_FILE`，但不能关闭 TLS 校验或把令牌交给不可信代发服务。DNS／TLS 错误先解决网络，不归类为账号失效。`auth status` 仅用仓库列表探测，不提供当前账号完整身份；身份需从已核实的平台账号／已有对象元数据另行确认。

## 更换令牌、退出与故障

更换或续期后重新执行 `ez auth login`，只更新当前平台记录。退出时：

```sh
ez auth logout
```

退出只删除当前平台的本机凭据，保留其他平台；不联网、不撤销 Ezone 上的令牌。需要撤销时由本人在平台处理。非空 `EZONE_TOKEN` 仍会生效，CLI 会提示；在设置它的终端执行 `unset EZONE_TOKEN`，CI 则修改对应机密变量。

- 缺少凭据／认证失效：按提示执行 `auth login`，或检查 CI 机密变量；不打印令牌排查。
- 登录成功仍无某项权限：登录只探测仓库列表，不证明合并、制品等权限足够，按实际请求核实。
- 环境令牌缺目标绑定：同时配置可信的 `EZONE_HOST` 或传 `--host`；改用已登录个人凭据时先清除遗留的 `EZONE_TOKEN`。
- 企业显示名称误填为标识：按平台确认的企业标识填写 `company`，不自行编码中文名称放入请求头。
- `doctor` 的来源与预期不符：核对当前工作目录、项目配置路径及环境覆盖；项目外可显式传入上下文。
- 权限过宽：macOS/Linux 按错误提示执行 `chmod 600 ~/.config/ezone/credentials.json`；格式损坏时先保留原文件再处理，不盲目覆盖。

## 已实现资源

| 资源 | 动作 | 限制 |
| --- | --- | --- |
| `repo` | `list/view/rules/release-template/compare` | 显式 repoKey，不从 remote 推断；rules 仅读取保护分支模式，完整审核要求另读设置 |
| `branch` | `list/view/create` | create 必须指定来源与引用类型，不提供删除 |
| `commit` | `list/view/compare` | 本地开发、提交、推送继续用 Git |
| `pr` | `list/view/create/edit/commits/changes/pushes/diff` | edit 仅标题和关闭／重开；完整 diff 先取 stat 再逐文件读取 |
| `pr` | `comments/reviews/reviewers/comment/reply/resolve/review/notify` | 行间与总评回复不同；投票不是合并；通知只表示请求已接受 |
| `pr` | `checks/pipelines/retrigger/merge` | 只返回事实，不判断门禁通过；merge 模式见动作帮助 |
| `pipeline` | `list/view` | repoName 是流水线服务路径名，不能由 repoKey 猜测 |
| `run` | `list/view/start/jobs/log/cancel/artifacts` | start 是异步请求；log 取文本日志；需回读终态 |
| `release` | `list/view/create/edit/upload` | 代码标签及版本说明；创建固定完整 SHA；upload 参数是标签 ID |
| `artifact` | `list/view/upload/download/release` | 仅 raw；package 是 pkgId，view/download/release 用 artifactId |
| `api` | 显式 HTTP 方法、同源路径、`--query`／`--input`／`--response` | 不自动分页，不增加授权，不绕过已知资源限制 |

列表默认单页，已提供分页的动作需 `--paginate` 才取全；`comments/reviews/changes/pushes` 等无分页开关的端点不假设分页。未知响应／不完整 diff 报错，不能据此宣称全量审查。正文支持 `--body` 或 `--body-file`（`-` 读标准输入），两者互斥；JSON 请求体使用 `--input FILE`。API bytes 响应必须指定 `--output`，不覆盖文件。

## 退出码

| 码 | 含义／后续动作 |
| --- | --- |
| 0 | 请求成功；对象状态仍需核对，不等于构建、门禁或业务验收通过 |
| 1 | 远端业务失败或无法确认读取结构 |
| 2 | 参数、环境上下文或输入错误 |
| 3 | 只读传输失败 |
| 4 | 认证缺失／失效 |
| 5 | 写入结果未知；先回读，不自动重试 |
| 6 | HTTP 权限拒绝 |

HTTP 200 仍检查整数业务 code，code=0 才解包 data；code=1000 视为认证失效，其他非零业务码原样报告（不能仅凭码猜权限）。写入不会自动重试。CLI 不改管理员、成员、保护规则、通知配置；项目／卡片、产品版本、部署和更多包协议未纳入本期资源命令。
