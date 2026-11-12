# PR 取证与交付

先读 [命令与环境](commands.md) 设置 `ez` 函数及环境。下列编号、路径、账号、版本和 40 位 SHA 均为示例，替换为现场已核实对象，逐阶段执行；不是可以整段运行的自动发布脚本。写命令仅在会话已授权相应动作和对象时执行。

## 发起、取证与审查

```sh
ez branch create feature/example --from 1111111111111111111111111111111111111111 --ref-type COMMIT
ez pr create --src feature/example --dest main --title '示例变更' --reviewer reviewer-account
ez pr view 2
ez pr commits 2 --paginate
ez pr changes 2
ez pr pushes 2
ez pr diff 2 --src 2222222222222222222222222222222222222222 --src-type COMMIT --dest 1111111111111111111111111111111111111111 --dest-type COMMIT
ez pr comments 2
ez pr reviews 2
ez pr reviewers 2 --paginate
```

上述 `pr create` 发起普通合并评审（MR）；[直接提交评审（DCR）](https://help.ezone.work/guide/code/term.html)由向保护分支 Git push 发起，没有普通源分支，继续使用原生 Git。DCR 的读取、意见或合并仅在确认真实评审对象与完整提交后复用相应命令；本期未真实验收 DCR，不假设普通源分支存在。

先从 PR、提交与分支事实确定当前 base/head，不以本地同名分支替代远端 SHA。diff 的 `--src/--dest` 是真实比较端点，PR 编号仅作上下文标记；必须自行核对端点与当前 PR 一致。统计显示截断、二进制／编码不支持或字段未知时明确覆盖缺口，不能静默遗漏。

审查规则复用当前环境的审查流程；平台取证不构成独立审查。在执行者自己实现或修复后，需另一评审者／上下文对原 base 到最终 head 作独立评审。没有等价能力时先完成取证、测试和草稿，暂停依赖独立结论的阶段。

## 总评、行间意见与原生通知

准备 UTF-8 正文文件。普通总评使用 NEUTRAL，APPROVAL／REJECTION 需单独核对投票授权；按当前环境的评论协议保留完整结论、证据范围及 base/head。已安装 `code-change-review` 时其评论模板是唯一格式来源。

```sh
ez pr review 2 --result NEUTRAL --commit 2222222222222222222222222222222222222222 --body-file review.md --at reviewer-account
ez pr reviews 2
ez pr comment 2 --path src/example.py --line 12 --commit 2222222222222222222222222222222222222222 --body-file inline.md --at reviewer-account
ez pr comments 2
ez pr reply 2 --comment-id 123 --body-file reply.md
ez pr reply 2 --vote-id 456 --body-file reply.md
ez pr resolve 2 123
ez pr comments 2
ez pr notify 2 --reviewer reviewer-account --type USER
```

行间回复先读取同一 PR 的父评论并沿用其 commitId/path/lineNum，不能将旧线程重锚定到新 head；总评回复用 vote-id，嵌套总评回复可加 `--parent-reply-id`。没有明确侧别参数，不套用 GitHub 的 LEFT／RIGHT 模型。解决只改状态，须在核验真实修复并获授权后执行。

写前核对账号身份、目标 PR、base/head、接收人及已有同身份评论。回读对象 ID、作者、完整正文、提交锚点和已核实的平台链接；Ezone 总评／行间评论分别读取，不以一次列表替代全部意见。返回中缺少的字段不能推断已经核对，必要时通过平台原生界面补证。

@ 与催审的 API 成功只能记为“已接受”；接收人未读页面／通知中心等观察到对应对象才记“已送达”，不能把总评 @ 的送达结果推给发布 @ 或催审。CLI 没有通知收件箱或已读查询命令。

通知、评论写入超时（exit5）先回读对应 PR 的评论／总评和可观察通知，按同身份、PR、head、正文、接收人去重；精确匹配则复用。只有远端证据证明未生效才可重试；无法证明时停留“结果未知”，不能因列表暂时空就重复 @。修改后刷新 head，复核旧意见处置和最终全量候选，复用仍等价的检查。

## CI、门禁、合并

```sh
ez repo rules
ez api GET /v1/code/v2/repos/123/settings/branch --query branchType=PROTECTION
ez api GET /v1/code/v2/repos/123/settings/branch --query branchType=COMMON
ez api GET /v1/code/v2/repos/123/settings/reviewer_rule
ez api GET /v1/code/v2/repos/123/settings/submit
ez pr checks 2
ez pr pipelines 2
ez pipeline list --repo-name directory/repository --paginate
ez pipeline view 10
ez run start --pipeline 10 --ref 2222222222222222222222222222222222222222 --ref-type COMMIT
ez run view 20 --pipeline 10
ez run jobs 20 --pipeline 10
ez run log --pipeline 10 --job 30
ez run artifacts 20 --pipeline 10
ez pr view 2
ez branch view main
ez pr merge 2 --mode CREATE_MERGE_COMMIT --title '合并示例变更' --body-file merge.md
ez pr view 2
ez branch view main
```

上述 API 示例的123替换为当前 repoKey；`repo rules` 只提供保护分支模式，不聚合分支审核要求或提交评审规则，需分别读取 branch 设置、reviewer_rule 审核规则与 submit 提交设置。关联构建必须对应被审查提交及目标分支；启动成功不是构建完成。run view 的失败状态是所查询对象事实，即使查询 exit0 也不能算构建通过。空流水线不是绿色 CI；未知门禁不是允许合并。明确项目所需检查以及无 CI 时已有的验收决定；项目不要求 CI 且适合变更的本地等价验证已满足时，可按既有授权继续并披露“未配置 CI”，不新增所有 PR 必须有 CI 的政策。缺少必需证据则暂停合并，不自行修改保护规则。

合并前核对当前规则、评审、门禁、源／目标 SHA、合并树及现有授权。事实变化只使受影响证据失效，不机械重跑所有测试。合并超时先查 PR 是否已合并及实际目标分支提交；未确认结果时不能重发。合并完成必须保留实际合并 SHA，不能默认原 head 或“最新 main”就是发布基准。

## 代码标签、附件与 raw 制品

`release create`／`release edit` 必须同时提供正文（`--body` 或 `--body-file`）和通知选择：要通知时用 `--at MEMBER`，不通知时显式用 `--no-notify`，不能省略两者。只授权创建标签、未授权接收人通知时使用无通知形式，例如：

```sh
ez release create v0.1.0-test --commit 3333333333333333333333333333333333333333 --body-file release.md --no-notify
```

若已授权通知接收人，下面带 `--at` 的创建命令是替代形式，不要对同一标签执行两次创建；随后按实际需要处理附件／制品：

```sh
ez release create v0.1.0-test --commit 3333333333333333333333333333333333333333 --body-file release.md --at reviewer-account
ez release view v0.1.0-test
ez release upload 70 --file dist/example.zip
ez release view v0.1.0-test
ez release edit v0.1.0-test --body-file release.md --no-notify
ez artifact list --package 40 --format raw --paginate
ez artifact upload --package 40 --format raw --version 0.1.0-test --file dist/example.zip
ez artifact view 50 --format raw
ez artifact release 50 --format raw --version 0.1.0
ez artifact view 50 --format raw
ez artifact download 50 --format raw --output /tmp/example-verified.zip
```

标签／说明回读需核对固定合并 SHA、正文、atMembers 及附件关联；发布通知单独确认送达。标签附件上传使用标签 ID，不能拿名称或 artifactId 代替；创建时已存在的附件 ID 可用 `--attachment`／`--note-attachment` 关联，上传后实际关联仍需回读核实。

raw 上传先检查版本明确不存在才发送；仍有并发检查窗口，严格禁止覆盖需平台规则保证。下载不覆盖已有文件，只表示保存了原生 bytes 响应；对照制品元数据核对内容、预期大小及本地 SHA-256（如 `shasum -a 256`），不能把下载成功当制品正确。记录包／制品 ID、版本、状态、来源提交、文件及校验和证据。没有源码关联字段时用构建记录和校验和补证，不能自造关联。

仅标签不代表产品版本或制品发布；本期未提供产品版本命令。如果任务要求的制品服务不可用，准确报告标签已完成和制品受阻，保留错误，不宣称完整发版。CI、通知、合并或制品真实环境验收尚缺时逐项列出，不用离线测试代替。
