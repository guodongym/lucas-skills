# Ezone Skill 与随包 CLI Implementation Plan

> 历史计划（2026-11-12 已执行）：当时的仅环境认证和不发布授权已由后续用户决定更新。当前配置与认证、公开仓库发布边界见 [2026-11-13 计划](2026-11-13-ezone-config-auth.md)。

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 交付可单独复制分发的 Ezone Skill 和 CLI，覆盖 PR 发起、审核、意见往返、原生通知、CI／门禁、合并、版本及所需制品发布；完成离线与分发验证，准确保留认证和真实写验收缺口。

**Architecture:** CLI 唯一源码位于 `skills/ezone/scripts/`，由 `ezone.py` 注册资源命令，`ezone_client.py` 负责 HTTP、业务响应、文件输入、分页与错误；`ezone_pr.py` 和 `ezone_release.py` 分别承载 PR 与交付命令。Skill 负责判断与串联流程，复用已有审查和发布规则；CLI 不自动决定是否批准、合并或发布。

**Tech Stack:** Python 3.11+ 标准库、argparse、urllib、unittest；沿用仓库已有 YAML 校验环境，不新增运行依赖。

**Spec:** [能力盘点及已确认方向](../../ezone-capability-inventory.md)。本计划独立记录实现所需约束和验收，不另造重复 spec。

## Global Constraints

- CLI 唯一实现位于 `skills/ezone/scripts/`；复制完整 `skills/ezone/` 后可从任意工作目录运行，无须安装 lucas-skills 包、第三方依赖或读取源仓库 `.git`。
- Python 3.11+；本地 Git 操作继续使用 Git。默认不创建全局短命令，不修改 `pyproject.toml` 或 `uv.lock`。
- 原生通知仅使用 Ezone；不接 WPS／邮件，不自动创建令牌或修改通知配置。
- 凭据只从 `EZONE_TOKEN` 环境读取，使用 `access_token` 请求头；不接受 URL、命令参数或日志中的令牌，不关闭 TLS 校验，不跨来源重定向传递凭据。
- 用户已批准实施和方向，并随后提供临时令牌要求直接测试。真实写验收限定 消费项目 专用测试分支／PR／预发布对象、通知本人；不触及 main、生产部署、权限／保护修改、本实现分支 push／merge 或既有数据清理。命令能力实现与真实执行验收分别报告。
- 仓库身份以显式 `--repo <repoKey>` 或 `EZONE_REPO` 为准；Git remote 只用于展示候选上下文，不猜 repoKey。主机、企业分别支持 `--host`／`EZONE_HOST`、`--company`／`EZONE_COMPANY`。
- 所有命令支持 JSON 输出；标准错误用于诊断。HTTP 200 仍须验证业务 `code`；包装成功码采用官方流水线示例中的整数 `0`，当前代码服务认证已确认成功码0。文本／文件端点显式选择响应模式。
- 不自动重试写入；超时／断连可能已经生效时报告“结果未知，先回读”。通知请求成功不等于用户已收到。
- 完整 PR 差异必须按 diff stat 的文件清单逐文件获取，不能把单文件接口当全量 diff；未知响应结构必须报缺口，不静默漏文件或分页。
- 代码库管理侧仅补本链路所需读取及明确分支创建，不提供删除仓库、改成员／权限、改保护规则或管理员内部接口的资源命令。

## Review Focus

1. 只复制 Skill 后仍隐式依赖工作目录、仓库包、第三方库或其他未安装 Skill：Task 1／4 用独立目录和子进程验证。
2. HTTP 200 业务失败、无 code 的未知响应、凭据重定向／诊断泄露：Task 1 覆盖 HTTP 边界和脱敏。
3. 满页、重复页、未知分页结构与两套分页参数导致遗漏／死循环：Task 1／2 覆盖列表与提交分页；不对未经定义的树形结构自动分页。
4. 行间意见侧别、解决状态、总评投票和发布 @ 被混淆：Task 2／3 验证真实请求字段，Skill 明示投票不等于合并、API接受不等于通知送达。
5. 写入超时、主分支变化、未知门禁、发版基准漂移：Task 1／2／3 测试未知结果无重试，Task 4 场景核对刷新与授权；创建发布显式指定提交，不默认最新 main。

## 确认的实现边界

优先提供确定性资源命令，不建立“一键批准合并发布”总命令。完整链路由 Skill 在授权和独立复核满足后串联。

CLI 公共接口：`python3 <Skill>/scripts/ezone.py [--host HTTPS_ORIGIN] [--repo REPO_KEY] [--company NAME] [--json] <resource> <action>`。全局选项放资源前，文档给清楚示例。`--version` 不触网。`doctor` 只读本地环境，不输出凭据。正文提供直接文本与文件／标准输入（互斥）形式；JSON 请求体用 `--input FILE`，`-` 表示标准输入。

输出保留服务原始数据，不在未知字段上伪造统一 PR／门禁／CI 状态。退出码：0 成功，1 已知远端／业务失败，2 参数／输入失败，3 只读传输失败，4 认证缺失／失效，5 写入结果未知，6 权限拒绝。没有能力证明的成功不能返回业务“通过”。

`Client.request(method, path, *, query=None, body=None, response="json", write=None)`：返回解包后的 `data`；JSON 模式要求可信业务包装，`code` 必须是整数；非零抛 `EzoneError(message, exit_code)`。`response="text"/"bytes"` 只给明确的文本／下载端点使用。`write` 显式区分特殊 POST／PUT 查询，默认按 HTTP 方法保守判定。

`Client.paginate(path, *, query=None, style="page", page_size=100)`：只用于文档定义了分页参数的列表。支持直接数组或 `data.list` 数组；可利用真实存在的 `total`，否则以短页／空页结束。`style="offset"` 使用 offset／limit。重复满页或结构不识别报错，不返回半份成功。所有列表默认单页，`--paginate` 才取全；明确输出或文档说明单页状态。

`Client.upload(path, fields, file_path, *, file_field="file")`：标准库 multipart，文件不强制读入内存；响应沿用业务／传输判错。下载使用明确输出路径，失败不覆写已有文件。对原生制品不同返回类型单独核对，不为格式统一而强制 JSON。

资源模块接口：`add_commands(subparsers)` 注册命令并用 `set_defaults(handler=...)`；handler 为 `(client, args) -> object`。`ezone.py` 创建 Client、调用 handler、输出和统一处理 EzoneError。公共帮助函数留在 client 模块，资源模块不相互调用。

## Task 1: 可独立分发的 HTTP 客户端与仓库基础命令

**Files:** Create `skills/ezone/scripts/ezone.py`, `skills/ezone/scripts/ezone_client.py`, `tests/test_ezone_client.py`, `tests/test_ezone_repo.py`。

**Interfaces:** 产出上述 Client／EzoneError／add_commands 约定，以及共享的仓库路径编码、正文文件读取帮助函数；确切函数名由实现者写入报告，后续任务据此复用。后续模块由入口正常 import，不依赖仓库 PYTHONPATH。

- [x] 先写并运行失败测试：认证缺失；业务 code=1000、非零与未知包装；权限拒绝；TLS／重定向；写入断连仅一次并返回5；JSON／文件输入错误；page与offset分页；未知结构／重复页；从独立目录运行帮助／版本。
- [x] 实现最小 HTTP／输入／错误机制，安全 HTTPS origin，令牌只进请求头。用官方成功例支持 code=0，业务错误保留 code 和已脱敏信息。源码不包含内部文档全集。
- [x] 实现 `doctor`、`auth status`（仅认证探测，不宣称全部权限）、`api`（显式方法／query／input／响应模式，不自动分页未知端点）。
- [x] 实现 `repo list/view/rules/release-template/compare`、`branch list/view/create`、`commit list/view/compare`；所有方法／参数查 `/tmp/ezone-api-v2.json`，保护设置只读。创建分支要求明确基准。
- [x] 运行本任务测试并记录 RED／GREEN 与测试数量；提交本任务，正文含动机、`验证：` 和 `Co-authored-by: OpenAI Codex <noreply@openai.com>`，不 push。

## Task 2: PR、审查意见、原生通知与合并命令

**Files:** Create `skills/ezone/scripts/ezone_pr.py`, `tests/test_ezone_pr.py`; Modify `skills/ezone/scripts/ezone.py`。

**Interfaces:** 使用 Task 1 Client／EzoneError／正文读取／路径帮助；产出 `ezone_pr.add_commands(subparsers)`。所有资源命令以服务事实为准，不自动下结论或修改门禁。

- [x] 先写失败测试覆盖各类请求映射和关键边界，再实现。外部 HTTP 边界可合成响应，实际调用生产 Client／handler，不复制算法。
- [x] 实现 `pr list/view/create/edit/commits/changes/pushes`；创建提供源目标分支、标题、通知评审人；状态编辑不暴露 MERGED 假合并，关闭／重开按实际 API 状态。
- [x] 实现 `pr diff`：显式源／目标引用及类型；先取 stat 再逐文件取 diff，包含新增／删除／重命名等实际路径；不能从未知 PR 字段猜源目标。必要时要求用户从当前 PR 事实显式提供引用，清楚报错。
- [x] 实现 `pr comments/comment/reply/resolve/reviews/review/reviewers/notify`；总评 APPROVAL／NEUTRAL／REJECTION，回复总评用 vote_replies，行间回复用 parentCommentId；resolved 是评论更新字段；@ 使用 atMembers。区分总评与行间意见，不虚构 side 参数。通知进行中评审的前提在帮助与引用中说明。
- [x] 实现 `pr checks/pipelines/retrigger/merge`；checks 保留原始 gate 事实。merge 使用带 reviewSeq 的继承请求体，显式合入方式、title及完整message，不改 PR status 伪造合并，不自动批准或重试。CI未配置不能报通过。
- [x] 验证标准输入多行、分页超过50条提交、路径编码、完整diff、错误退出和未知写结果；提交并报告。

## Task 3: 流水线、版本说明、附件及制品发布

**Files:** Create `skills/ezone/scripts/ezone_release.py`, `tests/test_ezone_release.py`; Modify `skills/ezone/scripts/ezone.py`。

**Interfaces:** 使用相同 Client／输入帮助；产出 `ezone_release.add_commands(subparsers)`，不依赖 PR 模块内部逻辑。

- [x] 先写失败测试，按 `/tmp/ezone-{api-v2,pipeline-api,package-api}.json`（实际文件名现场核对）及官方流水线成功例核对参数；不得硬猜返回字段。
- [x] 实现 `pipeline list/view`、`run list/view/start/jobs/log/cancel/artifacts`，必要的构建／作业／企业／repoName 明确输入；启动显式 COMMIT／TAG／BRANCH 基准，保留异步状态，不把启动成功当构建成功。日志若非包装JSON则按定义文本模式。
- [x] 实现 `release list/view/create/edit/upload`：基于代码标签及 releaseNote，创建显式提交、名称、说明、通知对象，附件走已定义接口；回读与外部验证步骤留清楚。无已证实平台能力时不把标签创建宣称产品版本或制品发布。
- [x] 实现 `artifact list/view/upload/download/release`，优先 raw 通用制品，直接使用公开业务接口；明确制品ID／格式／版本。Maven／镜像等继续原生工具，不建立完整包协议客户端。原生下载／上传返回形式与包装JSON不同则显式处理；覆盖行为不能靠默认值猜测。
- [x] 验证来源提交固定、@及附件映射、文本日志、下载失败不覆盖、multipart大文件不整文件入内存、业务失败／异步失败与写超时；提交并报告。

## Task 4: Skill、工作流适配、消费说明及离线验收

**Files:** Create `skills/ezone/SKILL.md`, `skills/ezone/agents/openai.yaml`, `skills/ezone/references/commands.md`, `skills/ezone/references/pr-release.md`, `skills/ezone/evals/evals.json`, `tests/test_ezone_skill.py`; Modify `README.md`, `skills/code-change-review/SKILL.md`, `skills/code-change-review/references/pr-comments.md`, `skills/review-and-release-pr/SKILL.md`（仅平台路径），及相应必要测试／盘点文档。

**Interfaces:** Skill 调用实际 CLI；不复制审查评分／发布规则。不强制依赖不存在的其他 Skill 才能启动，完整审查所需独立性仍须等价能力，缺少时只阻塞受影响阶段。

- [x] 先记录无 Skill 的代表性场景基线（可用前期现有 GitHub 专用流程作为受证据支持的限制，不制造失败）；创建运行／静态验收后观察缺少入口和便携性等失败。
- [x] 写精简中文 Skill：发现／认证／网络→锚定PR和授权→独立审核→意见核验与修复复审→原生通知→CI门禁→合并→基于合并提交发布与回读。真实写动作核对授权；刷新事实不等于强制重跑等价测试；未知状态不能批准。
- [x] commands引用只写已实现命令及限制；pr-release引用给完整可执行命令示例与原生通知送达／超时去重／发布验证步骤。以源码单一来源维护规则，不重复另一套审查准则。
- [x] 扩展现有评审 Skill 的后端选择和评论协议：GitHub仍走原路径；Ezone走平台Skill／CLI，保持同一身份、提交锚点、独立审查与评论回读要求。
- [x] 在README提供整体目录分发、Python／Git／令牌／网络条件、按路径调用、Agent Manager预览、来源版本回读。代码库额外能力清单标明本期／后续／不纳入，不能暗示管理员操作授权。
- [x] 用新的隔离场景验证完整链路与边界：只复制Skill；有评论需复审；无CI／未知门禁；通知或合并超时；仅有标签无制品；缺失独立review能力。实际Agent场景与CLI合成响应测试分别记录，脚本检查不替代场景。
- [x] 运行受影响和完整仓库 unittest，Skill元数据校验、全部文内本地链接、从仓库外运行CLI；提交并报告。不安装真实HOME、不触发真实外部写入；输出具体预览供已有授权核对。

## 验收与授权后续

当前实现、离线／分发测试、文档和逐步独立复核已完成；完整仓库333项通过，7个独立行为场景经6/7初轮及1/1补验满足。用户后续授权的隔离真实链路已完成PR发起、意见往返、修改复审、测试目标合并、代码标签和附件回读／校验，总评@通知已在本人接收端观察。详情见 [验收记录](../../ezone-validation.md)。

本机正常直连仍有DNS／证书路径问题；本次使用仅转发TLS密文的临时网络路径，未关闭验证，未把令牌交给中间主机。消费项目无CI配置、有效raw测试包未选定、发布通知送达等缺口仍保留（原制品查询4502已定位缺tabType条件并只读验证恢复），不宣称完整生产发布验收。项目内安装已由原生skills/list确认启用，最终整分支复核的唯一P1修复后已闭环；不执行真实HOME apply，不合并或push实现分支，不清理既有对象。
