# KB 检索两仓合并验收：已合代码，未部署

## 完成状态

2026-09-18 用户明确确认后执行。只处理以下两张 PR，没有合入其他在途任务：

| 仓库 | PR | 原 main | 被测且已合入的提交 |
|---|---|---|---|
| 知识库 | [#151](http://127.0.0.1:3300/a77/knowledge-base-private/pulls/151) | `8a413cde59cd0d6a7757c845243024a3016b50bc` | `dd51e87b1e6ff4072ba98451509b325fae3b0362` |
| 金融 | [#784](http://127.0.0.1:3300/a77/finance-workspace-private/pulls/784) | `0a1cb8c44aaf2d19ae5f5809bf27119b709b8442` | `e0467e3a5f6fb431a415c56f500556685cefbf6e` |

两仓主干没有分叉，Gitea `fast-forward-only` 均成功，PR 状态 merged。合后重新 fetch，确认
远端 main **等于**被测提交（不是仅代码树相等）。共享脏主检出、本地旧 main 指针及生产路径未切。
后续本文件及收据归档是 docs-only，不把上述严格 revision 收据冒充未来文档 HEAD 的全量重测。

## 按发现顺序

1. 开工检查共享工作树：金融有其他任务未跟踪内容；KB 有 ingest 改动及 `内蒙一机` 未解决
   冲突。均不认领、不暂存、不重置。原修复树干净，从候选提交另建一对标准仓名的隔离检出。
2. 建树前复制各仓自己的 pre-commit 至命令级 hooksPath，省略有副作用的 post-*，不改共享
   配置、不跳过提交门。建树前后及合入后核对普通 meta/chunks、全文 meta 三份生产指纹不变。
3. 最新 Gitea main 没有前进，merge-tree 无冲突。以 `env -i` 清除 launcher 变量、umask022，
   主金融 `.venv-workbench/bin/python` 跑 Python；跨仓显式 KB_RECEIPT_CODE_ROOT，遥测独立文件。
4. 第一次真实同级两仓 registry 检查报红：KB `rag-query` 已改摘要/触发词/内容 hash，金融
   `skills.registry.json` 还存旧值。旧阶段在不同目录验收漏掉这个组合，不是“本轮没有问题”。
   中断尚在执行的旧候选 Python，全量未完成**不算通过**；前端/KB已得的读数仍按原SHA记录。
5. 在金融原任务树用现有生成器绑定被验 KB 根重扫；第三仓 finance-research-site 只读用于
   完整登记（其 skills 为0）。断言只变 `kb/rag-query` 条目与 generated_at，不删缺仓条目，
   不顺带改其他技能。提交 `e0467e3a`，原 pre-commit 通过，再在干净检出完整重跑金融四叶。
6. 两仓测试全绿后，在已创建的 #151/#784 各留验收评论，通过 API 仅快进合入，指定 head_commit_id，
   不 force。fetch 后重新用 `--expect-revision gitea/main --base-drift-max 0` 验金融全量收据。
7. 只读 health 实测部署仍 `runtime.source_revision=bf662e9310ff751a4c31763815ee78fb7d6d5122`，
   `source_dirty=false`、`code_matches_repo=true`。首探把字段当顶层得到 null，未据此判服务异常；
   按当前 schema 的 runtime 节重新取值后保存。服务未重启、未调用生产索引 update。

## 决策

| 方案 | 采用与否 / 理由 |
|---|---|
| 在共享主树拉 main / 处理旧冲突 | 否：会混入他人内容，并可能触发旧 hook 写索引 |
| 沿用前一阶段 registry 通过 | 否：此次同级候选实测红，必须修生成结果后重验 |
| 缺第三仓时强制重扫 / 人工改 hash | 否：避免删条目或另造算法；用原生成器、显式绑定本次候选 |
| 普通 merge 造新提交、拿旧收据当新提交验收 | 否：编号不一致。两仓均满足快进条件，用仅快进保持精确SHA |
| 快进主干期间漂移就强推 | 否：API只允许快进，合前两仓ref核对；不满足就停下重验 |
| 合入代码顺便迁索引或切8792 | 否：迁移/部署有独立运维前置，工程绿不是生产效果证据 |

## 本轮验证（非独立模型QC）

本次为同一执行会话的隔离检出复验，不声称独立 agent 审查。

- 金融固定干净 `e0467e3a`：**11481 passed / 73 skipped / 2 xfailed / 0 failed**，17 warnings，
  707.24s；Ruff exit0。原始收据 `20260918T105656Z-e0467e3a.json`，dirty=false、整树0脏，
  Python3.12.13，解释器 `/Users/a77/finance-workspace-private/.venv-workbench/bin/python`，
  依赖指纹 `3328bed61f3e21ea`。合后8项一致性检查exit0，基座漂移0。
- 定向 **194 passed**，包含 KB真实CLI/真实worker临时hash索引三项，以及 registry绑定/解析测试。
- frontend lint/typecheck/build exit0，**107 tests / 8 files**；E2E **34 passed / 2 skipped**，
  独立18871/18874服务，RE06_E2E_URL同步；用例自建市场库与用户。服务结束后两个端口无监听。
- registry五项：parseability、check、tables、views、ledger crosswalk 全exit0；crosswalk有历史
  反向warning，未抬档或掩去。finance-research-site只读，未改其脏文件。
- 原金融 pre-commit 对完整 PR diff 通过，含层级、路径、字段、dataset、工具可达性及runtime目录。
- KB固定干净 `dd51e87b1`：**820 passed / 1 warning**，13.12s；strict-vocab 0错误/2既有告警，
  size/log-id/index-regression/quality/pre-commit 全通过；missing_wikilinks=3326，仍有历史债务。

持久原件：`docs/verification/2026-09-18-kb-retrieval-merge/`（金融）；KB对应
`docs/verification/2026-09-18-retrieval-merge/`。现场完整运行目录：
`~/.finance-runtime/reviews/kb-retrieval-merge-20260918/`，保留首次registry红与中断说明。

## 未完成 / 接手者下一步

代码合入已完成，旧 `fix/kb-filter-receipt` 在途交接删除转档至本快照；未部署工作不伪装成该
代码PR仍未合。KB原理与协议边界仍见 `2026-09-18-kb-filter-receipt.md`。

- 生产服务仍旧、KB主检出仍旧，旧绝对路径post-*继续有越树风险；仅合远端不会自动装上guard。
- 部署应单独冻结KB代码根和资料根、先让真实hook调用走保护，再受控更新双索引，保留各自
  model/include_raw/max_files，核版本/字段非空/白名单覆盖/冲突隔离/health，再重启消费服务。
- 历史13页正文混入未恢复，共享主树另页冲突不代解；保留隔离，不因MRR下降删标记放行。
- 未做真实BGE、多模式质量/延迟对照，未给全部问句自动加as_of，过滤仍走CLI。hash协议绿不是
  金融研究效果认证。正文恢复、索引覆盖和真实题集标注完成后再比较排序。
- 第一阶段旧hook曾触发普通生产刷新，历史披露不撤回。本轮“不变”只覆盖三份文件与本窗口。

## 沉淀

现有registry检查确实拦住组合漂移，无需再建相同门；需要的是按真实多仓布局执行已有检查。
测试驱动脚本只组合现有固定命令并记录exit，属本轮现场记录而非新增通用工具，未改共享harness。
