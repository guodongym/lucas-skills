# Ezone 研发全流程：能力盘点与实施建议

日期：2026-11-12。本文保留调查时的能力矩阵与拟议接口，作为历史设计依据。后续实施已获批准，当前实现入口见 [Ezone Skill](../skills/ezone/SKILL.md)，准确参数见 [命令引用](../skills/ezone/references/commands.md)及实际 CLI `--help`，本期／后续边界及真实验收见 [验收记录](ezone-validation.md)。下文“尚未实现／未认证”等描述均指调查当时，不代表最新验收结果。

本次修订：用户要求考虑“CLI 随 Skill 目录一起分发，别人拿到就能用”，并明确 PR 与发版全链路必须包含发起、审核、意见、通知、合并和发版；通知渠道已确认为 Ezone 自带通知。建议据此把 CLI 实现放入 Skill 的 `scripts/`，默认无需另行安装 CLI，并把完整 PR 到发版链路列为第一阶段验收；更广的研发流程保留后续阶段。

当前代码库边界：本期仅 repo／branch／commit 已实现资源与 MR 链路所需读取、显式分支创建；`repo rules` 仅读保护分支模式，审核要求另读公开设置。DCR 发起沿用向保护分支 Git push，无普通源分支；读取／意见／合并按实际对象和完整提交复用，未真实验收。文件树／内容／搜索／blame／归档／卡片关联列后续；删除及管理侧改库、成员权限、保护规则修改、镜像与 GC 不纳入，不因通用 API 存在而获得操作授权。

## 1. 目标、归属与现场

用户目标是参考 GitHub CLI，建立覆盖需求到交付与恢复的 Ezone CLI 和配套 Skill，在 lucas-skills 集中维护，由 消费项目 首先安装使用。第一期交付不能代表全流程完成。

建议归属：

- `skills/ezone/scripts/` 提供 CLI 的唯一实现，负责可确定的 API 操作、输入输出和失败语义。复制整个 Skill 后能按路径运行，不依赖本仓库的 `tools/`。
- `skills/ezone/SKILL.md` 及 `references/` 提供平台能力、命令选择、证据获取与流程串联；CLI 仍是独立进程入口，只是随 Skill 一起分发。
- 需求审查、独立代码审查、发布治理继续使用现有 Skill，只补平台适配，不复制规则。
- 消费项目 仅保存无密钥的仓库、项目、流水线、环境标识和自身验收规则；安装完整 Skill 的固定版本；项目部署脚本不迁入通用 CLI。

现场调查记录曾包含内部消费项目状态；公开版只保留能力、实现边界与验收条件。实际仓库标识必须通过所在实例认证查询，Git 地址不能直接证明 API 的 `repoKey`。

## 2. 证据及其限度

[官方系统 API 说明](https://help.ezone.work/guide/base/api.html)给出了各服务文档入口。通过已有 SSH 可达路径，在正常 TLS 校验下读取了下表实时 Swagger。SSH 服务器只是本次调查路径，不是拟议 CLI 的依赖。

| 服务 | 实例文档入口 | 路径数／操作数 |
| --- | --- | --- |
| 代码服务公开 v2 | `/v1/code/doc.html`，组 `1. api-v2` | 184／249 |
| 项目管理 | `/v1/project/doc.html` | 753／1042 |
| 流水线 | `/v1/pipeline/doc.html` | 75／97 |
| 制品库 | `/v1/package/doc.html` | 241／306 |
| 主机部署 | `/v1/deploy/doc.html` | 46／60 |
| Wiki | `/v1/wiki/doc.html` | 144／190 |
| 文档 | `/v1/doc/doc.html` | 177／199 |

统计包含文档中的内部、管理及重复方法映射，不是待实现命令数或可用能力数。代码服务 v2 与交接时保存的 JSON 内容一致；其余服务为本次新增核对。完整内部 Swagger 仅保存在 `/tmp/`，不提交仓库。Context7 未找到匹配的 Ezone 文档，不能用其返回的 Ozon 文档替代。

以下矩阵的 API 均已核对文档定义，未进行认证调用。代码服务 Swagger 路径是 `/v2/...`，外部访问须加 `/v1/code`；其他服务的下列路径已包含服务前缀。

## 3. 阶段、命令、权限与验收矩阵

权限栏的“读／写”表示所需业务能力；精确令牌范围及角色仍须实测。HTTP 方法不等于副作用分类，例如部分查询使用 POST 或 PUT。

| 阶段 | 用户操作 | 拟议 CLI 命令 | 已核对的代表 API | 所需权限 | 阶段验收 | 缺口 |
| --- | --- | --- | --- | --- | --- | --- |
| 需求与项目 | 查项目和卡片、新建、编辑、流转 | `project list/view`、`card list/view/create/edit/transition` | `POST /v1/project/project/card`；`PUT /v1/project/project/card/batchUpdateFields`；`PUT /v1/project/project/card/cardType/status/batch` | 项目／卡片读写及流转权限 | 可辨识测试卡片能查询、修改、按合法流程流转并回读；拒绝缺少必填字段的变更 | 自定义字段、类型、必填项、审批约束需读取项目 Schema 后验证；不能统一映射为 GitHub issue |
| 仓库与分支 | 定位仓库、查询和创建分支、本地开发 | `repo list/view`、`branch list/create`；本地继续用 Git | `GET /v2/repos`；`GET /v2/repos/{repoKey}`；`GET /v2/repos/{repoKey}/branches`；`POST /v2/repos/{repoKey}/branches` | 仓库读／分支创建 | 从 消费项目 remote 可靠定位仓库；显式覆盖上下文；仓库不明时不猜测 | 企业、目录、仓库标识转换和带 `/` 的分支编码待实测 |
| PR | 创建、修改、查看 PR | `pr list/view/create/edit` | `GET /v2/repos/{repoKey}/reviews`；`POST /v2/repos/{repoKey}/reviews`；`PUT /v2/repos/{repoKey}/reviews/{reviewSeq}` | PR 读写 | 测试 PR 源目标分支、标题与回读一致 | 创建字段有 `subject`，更新体主要为 `subject/status`，不能承诺 gh 同等正文编辑能力 |
| 差异与审查 | 读取提交、差异、总评和投票，发表／回复意见，标记解决，修改后复审 | `pr diff/comments/review`、`pr comment/reply/resolve` | `GET /v2/repos/{repoKey}/diffs`；`GET /v2/repos/{repoKey}/reviews/{reviewSeq}/commits`；`POST /v2/repos/{repoKey}/reviews/{reviewSeq}/comments`；`PUT /v2/repos/{repoKey}/reviews/{reviewSeq}/comments/{commentId}`；`POST /v2/repos/{repoKey}/reviews/{reviewSeq}/vote_replies`；`POST /v2/repos/{repoKey}/reviews/{reviewSeq}/votes` | 差异／评论读取，评论／投票写入 | 完整差异、当前提交、评审身份可核对；意见可回复并按实际处理结果标记解决；改动后复审以最新提交为准；经授权发布后回读内容与位置 | 更新评论体含 `resolved`，实际权限及线程状态待实测；旧／新侧定位和过时语义不能套用 GitHub；交接记录的总评 1000 字限制未由本次 API 实测确认 |
| 原生通知 | 发起时通知评审人、催审、意见 @、发布 @ | `pr create` 的评审人参数、`pr notify`、评论／发布命令的通知参数 | `POST /v2/repos/{repoKey}/reviewers/notify`；创建评审体的 `notifyReviewers`；评论及标签请求体的 `atMembers` | 通知评审人／评论／发布权限，具体范围待实测 | 发起通知、催审、意见通知、发布通知均有明确接收对象和实际可观察结果；发送失败不改写业务操作结果 | 催审接口只允许进行中的评审；@ 字段不证明通知已送达；合并通知、用户订阅及发版通知实际行为待验证；本次不接外部消息渠道 |
| 合并 | 查门禁、批准后合并 | `pr checks`、`pr merge` | `GET /v2/repos/{repoKey}/review_gate/{reviewSeq}`；`POST /v2/repos/{repoKey}/merge` | 门禁读取／合并权限 | 刷新当前提交和门禁，针对新测试 PR 经授权合并，核对目标分支及合并提交 | 请求定义通过继承提供 `reviewSeq`，实际接收行为待验证；禁止用改 `status` 代替 Git 合并；已合并的 消费项目 PR !1 不作盲测对象 |
| CI | 列流水线、启动、看构建／日志、取消 | `pipeline list/view`、`run list/view/start/log/cancel` | `GET /v1/pipeline/pipelines`；`POST /v1/pipeline/pipelines/{id}/manual`；`GET /v1/pipeline/pipelines/{pipelineId}/builds/{recordId}`；`GET /v1/pipeline/pipelines/{pipelineId}/jobs/{jobId}/logs`；`POST /v1/pipeline/pipelines/{pipelineId}/builds/{recordId}/cancel` | 流水线读取／触发／取消权限 | 明确区分流水线、构建、作业标识；异步运行至终态，取全日志，失败返回非零 | 运行参数、日志增量与终止、权限和 PR 提交关联待实测；不能把未配置检查当作通过 |
| 版本发布 | 标签说明、产品版本及其关联 | `release list/view/create`、`version view/release` | `POST /v2/repos/{repoKey}/tags`；`GET /v1/project/project/version/{id}`；`PUT /v1/project/project/version/{id}/release` | 标签／产品版本读写与发布权限 | 区分代码标签、产品版本、制品版本；按所选对象创建并回读说明、提交及关联 | Ezone 发布不是单一 GitHub Release 对象；标题与完整合并提交信息不可混淆 |
| 制品 | 查版本、上传／下载、发布 | `artifact list/view/upload/download/release` | `GET /v1/package/api/artifact`；`POST /v1/package/api/artifact/release`；`GET /v1/package/pkg/{companyName}/{repoFormat}/{repoName}/{repoType}`；`POST /v1/package/pkg/{companyName}/{repoFormat}/{repoName}/{repoType}` | 制品库读／上传／发布权限 | 下载校验一致；明确版本、仓库和覆盖策略；发布后回读来源 | 不同制品格式的上传／发布合同不同；镜像优先沿用原生客户端，不先重写协议 |
| 部署与恢复 | 查上线单、创建、审批／执行、日志、取消／重试 | `deploy list/view/create/start/log/cancel/retry`；恢复方式另核验 | `GET /v1/deploy/groups/{groupId}/tasks`；`POST /v1/deploy/groups/{groupId}/tasks`；`POST /v1/deploy/groups/{groupId}/tasks/{taskId}/deploy`；`GET /v1/deploy/groups/{groupId}/tasks/{taskId}/logs`；`POST /v1/deploy/groups/{groupId}/tasks/{taskId}/retry/{id}` | 部署读取／创建／审批／执行等分别验证 | 在隔离环境关联明确制品与目标机器，记录终态与健康检查，并验证恢复后的版本及数据 | 任务体有失败自动回滚 `autoRollback`，但未确认独立手动回滚接口；重试不等于回滚。`serverIds` 省略代表全部机器，命令须明确目标范围。主机部署文档不证明 KCE／容器部署可用 |
| 文档与追溯 | 查文档、编辑／发布、连接卡片、PR、构建与制品 | `wiki view/edit/publish`、`doc list/view`、`link list/add/remove` | `PUT /v1/wiki/wiki/page/{id}/release`；`GET /v1/doc/space/{spaceId}/file/{fileId}/relation`；`POST /v2/repos/{repoKey}/integration/cards`；`GET /v1/pipeline/pipelines/{pipelineId}/builds/{recordId}/cards` | 文档／关联读写及发布权限 | 卡片→PR→提交→构建→制品→环境可追溯；改写前获取版本，写后回读 | Wiki 与文档不是同一模型；编辑并发、正文格式、附件及最终部署关联待验证 |

质量检查与测试：本地构建、测试和 lint 继续复用各项目工具；扫描／测试管理服务的官方文档入口已找到，但本轮未核对其 API，列为全流程覆盖缺口，不隐含纳入已完成能力。K8s 官方文档入口为 `/v3/k8s/doc.html`，同样尚未核对。

## 4. 最小复用方案与替代方案

推荐沿用 Python 3.11、`argparse`、标准库 HTTP 和 `unittest`，但调整分发边界：CLI 的唯一源码归属 `skills/ezone/scripts/`，通过 `python3 <Skill绝对路径>/scripts/ezone.py ...` 运行。根据实际复杂度在该目录内拆模块，不复制另一份到 `tools/`。不依赖 lucas-skills 的虚拟环境或工作目录，不要求 `uv sync`，首期不新增第三方依赖，不做 MCP 或网页控制台。现有 Agent Manager 自动扫描 Skill，可直接复用安装管理，无须修改其业务职责。

[Agent Skills 格式规范](https://agentskills.io/specification)明确支持随目录分发可执行 `scripts/`，并要求脚本自包含或清楚声明依赖。因此“拿到 Skill 就能用”指拿到完整目录且环境具备 Python、Git、可信网络和个人令牌，不是只复制一份 `SKILL.md`，也不是免去运行时和账号权限。

原建议的仓库级安装包可提供短命令，但要求使用者另外安装 lucas-skills 工具包，与此次分发目标不符，故不作为默认方案。单独 CLI 仓库利于独立版本和多人发布，当前尚无对应需求证据，也不优先采用。若以后用户需要直接输入 `ezone ...`，再提供指向同一实现的可选入口；短命令安装不是 Skill 能运行的前置条件。

借鉴 [gh api](https://cli.github.com/manual/gh_api) 的资源子命令、显式仓库上下文、JSON 输出、正文文件／标准输入、分页与通用 API 入口，以及[可靠退出码](https://cli.github.com/manual/gh_help_exit-codes)。不照搬 GitHub 的认证、分页响应和评审线程模型。

拟议的公共约定，须在正式设计中定稿：

- `--host`、`--repo` 显式覆盖项目上下文；从 Git remote 推导的只是不含密钥的候选上下文，无法确认时要求明确标识。
- `--json` 保持机器可读，诊断进入标准错误；正文支持文件和标准输入，避免 shell 引号破坏多行内容。
- `api` 接受明确的方法、服务路径、查询及请求体；通用入口不是授权绕过手段。只对已证实的查询端点提供自动分页，不假定所有接口具有相同结束条件。
- 凭据首期使用进程环境中的 `EZONE_TOKEN`，通过 `access_token` 请求头发送。不得进仓库、URL、命令参数、日志或跨来源重定向；不自动提取 Cookie，也不创建或扩大令牌权限。
- 同时检查 HTTP 与业务响应。认证缺失、拒绝、业务失败、传输失败、异步未结束、写入结果未知须可区分；超时写入先回读，不盲重试。
- 未认证或未验证的接口不得标记为可用；JSON 输出需保留检查缺失／能力未知，不能统一转为成功。
- CLI 的版本信息和来源随 Skill 目录一起携带，移动或复制目录后仍可回读；默认共同升级，避免 Skill 指令与工具分开更新。不能依赖来源仓库 `.git` 才能运行或显示版本。

## 5. 分期与完成定义

| 阶段 | 交付 | 退出条件 |
| --- | --- | --- |
| 当前调查 | 本文、归属建议、能力／缺口与安装方案 | 已明确原生通知和必须覆盖的 PR／发版链路；按修订方向补完整设计及可执行计划 |
| 第一期：消费项目 的完整 PR 与发版链路 | 随 Skill 分发的 CLI、认证状态／网络诊断、仓库上下文、通用 API；PR 发起与更新、审核、总评／行间意见、回复／解决、修改后复审、原生通知、CI／门禁、合并；标签与发布说明、所需附件／制品及发布通知；Ezone Skill 与现有评审／发布流程适配 | 从测试分支发起 PR，通知评审人，完整处理一轮意见并复审，在 CI／门禁及授权满足后合并，基于核对过的合并提交发布并确认原生通知。仅复制 Skill 的隔离验收、离线测试、认证只读均有证据；写入在明确授权的新测试对象上验证。任何必需环节尚未验证就报告缺口，不把“仅 PR”算作本期完成 |
| 第二期：需求与交付关联 | 项目／卡片、更完整的独立 CI 运行与日志、产品版本和更多制品格式、需求关联 | 在授权范围建立卡片→PR→构建→制品的可追溯链路，验证合法流转、分页、失败和重复操作 |
| 第三期：环境交付与恢复 | 环境识别、部署状态／日志、获准部署操作、与项目已有恢复步骤衔接；文档及追溯补齐，核对所需扫描／测试管理能力 | 消费项目 隔离环境完成部署、失败定位和实际恢复；验证文档关联与版本一致。KCE／容器路径按现场确认，不把主机部署接口视为通用适配 |

全流程完成要求：每个纳入范围的用户动作都有可发现入口、真实 API 或现有工具路径、权限说明、对应验证和明确失败语义；消费项目 完成一条从需求到交付与恢复的真实可追溯链路。接口文档覆盖、离线测试、认证只读、外部写入、安装和业务验收分别报告。未验收阶段继续列为未完成，不因存在 `api` 通用入口而宣称完成。

不预先承诺工期：当前缺少认证响应、消费项目 流水线／环境实际配置和恢复验证条件。

## 6. 安装与 消费项目 消费建议

默认只分发／安装完整 Skill 目录，CLI 随目录到达并共同升级；可发现性与可执行性仍分别验证。以下均为实施后的操作方案，当前尚未执行：

1. 在隔离任务工作区完成实现和测试，将整个 `skills/ezone/` 复制到与本仓库无关的临时目录，切换到另一个工作目录，以脚本绝对路径执行版本、帮助、自检和离线场景；不靠 `PYTHONPATH`、本仓库 `.venv`、`tools/` 或源码软链补齐文件。此检查用于证明别人拿到完整目录也能运行。
2. 首个项目通过现有 Agent Manager 管理 Skill：`uv run agent-manager skills set ezone --tool codex --on --json` 先预览，再按已有批准执行应用。默认从集成后的固定主工作区加载，避免长期链接将被删除的任务 worktree；新建 Codex 会话确认 Skill 被发现及来源路径。其他使用者可将完整目录交给其 Agent 支持的 Skill 安装方式，无须安装 lucas-skills Python 包。
3. 人在终端也可以直接调用同一脚本，例如 `python3 <Skill绝对路径>/scripts/ezone.py pr view <编号>`；`<...>` 是待替换位置。全局短命令作为以后按需增加的便利入口，当前不新增第二套打包维护路径。
4. 使用者仍需 Python 3.11+，本地代码操作需 Git，并有 Ezone 的可信网络及适当令牌权限；Skill 启动诊断给出缺项，不悄悄装依赖或修改系统。其他评审／发布 Skill 优先复用，但 CLI 启动不以它们存在为前提；完整流程所需的独立复核等能力缺失时，寻找等价路径或明确阻塞，不宣称已完成审核。
5. 用户已表达“当前项目安装使用”的目标；执行时仍须展示具体安装对象及冲突预检。若使用现有管理器，README 明文要求真实 HOME 写入先预览、单独确认；已有明确批准且同一预览、范围和风险未变化时不重复询问。
6. 消费项目 只提交无密钥上下文；当前认证方案见 [命令与环境](../skills/ezone/references/commands.md)，历史调查中的仅环境方案已被个人凭据支持扩展。实际 `repoKey`、项目、流水线、制品库、环境及命名空间通过认证只读查询确认后填写，不由目录名推测。消费验收不修改其 `.scratch/`、真实配置、部署记录或业务代码。

## 7. 权限、网络及高影响缺口

- [官方个人设置说明](https://help.ezone.work/guide/base/personalSetting.html)支持个人令牌和 `access_token` 请求头；Swagger 未定义足够的令牌范围与业务角色映射。首次认证先读，不为测试自动创建令牌或申请写权限。POST／PUT 查询所需的令牌写范围是否与业务只读冲突，须实测确认。
- 当前终端直连报 TLS 主机名校验失败。SSH 路径可读文档不代表本机网络问题已解决；CLI 正式使用须有可达且证书正确的网络路径，不内置调查服务器或关闭校验。
- 交接中的未认证请求为 HTTP 200 加 `code=1000`。本次读到的代码服务响应只宽泛声明 `code/data/message`，未定义成功码或具体数据结构；认证后的实际样例是实现业务判错和分页前的必要输入。
- 代码服务存在页码分页与偏移分页；跨服务还可能返回文本、下载流及不同 JSON 结构，必须按端点验证。内部接口、管理接口、回调和弃用接口不作为缺口的默认补法；尤其不能按 GET 一律判只读。
- 跨服务还需核对企业标识 `x-company-name` 及原生制品接口的认证方式，不能假定只有令牌就能调用全部服务。项目卡片状态接口明确可能要求补必填字段、发起审批或等待审批；保留这些业务失败，不自动绕过。
- 部署任务的 `autoRollback` 仅承诺失败时回到上次成功版本，仍须验证其项目适用性与数据恢复；未指定 `serverIds` 会作用于全部机器，执行前必须有明确目标。Doc 树查询默认递归、Wiki 发布版本冲突也须单独处理，不能套用代码服务的分页和编辑逻辑。
- 合并继承请求体、行间评论侧别、评审线程状态、卡片 Schema／审批、不同发布对象、原生回滚及 KCE 路径仍有缺口。无法映射的行为明确说明，不伪装为 GitHub 等价能力。
- 消费项目 的 Compose／KCE 文件是环境方案，不是已部署证据。是否由 Ezone 托管实际部署、具体流水线和恢复路径尚未查明，不据此引入新的部署系统。
- 本任务尚未授权真实评论、投票、合并、发布、部署、权限扩大或清理。可实现及离线验证这些命令，但真实外部写入须核对具体对象与既有授权；不继承旧 PR 的授权。

## 8. 预计改动与验证范围

实现时预计触及 `skills/ezone/`（包含 CLI、引用资料及必要的随包离线检查）、`tests/test_ezone*.py` 和合成样例、两个现有评审 Skill 的平台取证／评论适配及相应测试，以及 README。独立发布 Skill 所需的资料必须随包或明确声明，不允许悬空引用 lucas-skills 源码。

本方案不增加仓库级 CLI 入口，因而不需要为 Ezone 修改 `pyproject.toml`、`uv.lock` 或现有两个入口的布局断言。Agent Manager 自动扫描 Skill，正常情况下不需要增加 Ezone 专用运行时代码。仓库测试必须覆盖只复制 Skill 目录后的实际 CLI，不能仅在仓库根目录导入成功。

必须验证实际内部实现的参数、HTTP／业务错误、认证缺失、权限拒绝、两类分页、正文文件／标准输入、JSON 与退出码、超时写入不确定性及安装后运行。外部服务使用合成响应隔离；认证实测和真实写入另记，不能由模拟测试替代。现有评审准则、独立复核和发布授权约束保持同一来源。

本轮仅新增本文；未实现、安装、提交、push 或执行真实 Ezone 业务读写，也未修改 消费项目。
