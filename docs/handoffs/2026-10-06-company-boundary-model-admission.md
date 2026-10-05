# 2026-10-06 · 公司上下文边界与 Workbench 响应模型准入

## 背景与本轮边界

继续 PR [#52](https://github.com/moscrol/finance/pull/52)，分支 `fix/harness-budget-unconstraint-1005`。前轮完整 marker 绑定修复见 [10-05 快照](2026-10-05-grounded-binding-boundaries.md)，预算与引用记账背景见 [接手记录](2026-10-05-harness-budget-takeover.md)。本轮解决两项可分离的工程问题：公司上下文误报不能靠放宽身份边界解决；真实 Workbench 产物不能靠配置的模型名证明实际响应身份。

**三张账分开：工程检查、真实入口/响应身份、回答质量。** 本文的最终源码身份为 `b5c3d4fa8544f489b024dd78aae9cf93119b4334`，已推 GitHub，本机完整 Python 门禁和该头 GitHub 五项检查通过。两份既有 live 首稿的响应身份通过，**回答质量仍未通过**。本轮公司修复、模型准入、重放和门禁没有新增模型请求；前一阶段的两次 live 请求不能改记成零。

用户保留最终合并决定；没有合并、部署或回收真实工作树。生产 8792 未改动。FINANCEWORKS-6 保持 `in_progress`，FINANCEWORKS-13 保持 `in_review`；局部工程不能代签父任务。

## 按发现顺序

1. 完整 marker 边界修复后，隔离 8796 按冻结题面各首发一次：D4 `run_20261005_234226_342740`、D1v23 `run_20261005_235746_803448`。未重采追绿。D4 原稿里的“为重点的综合医药健康集团”“算力方向的三环集团”被公司提取器当成新名字；证据实际有对应描述/公司。此时不能把所有错误都归给写手。
2. 初稿想在被提取字符串内部搜索“中/为/的”等切点恢复短名称。反例表明“华中三环集团”“华为三环集团”“新三环集团”会借“三环集团”证据误放，故否决。`8916a87cf` 将上下文恢复限制到**开头完整引导短语**，且当前绑定证据须支持恢复后的名字。
3. 继续压测发现惰性匹配会把“三环集团银行”“中信证券集团”“丽珠集团股份”截成较短已知名字。`89527d47c` 恢复贪婪匹配，只在公司后缀紧邻显式列表连接词 `和/及/与` 时拆相邻公司；恢复路径增加证据左边界和长名称后缀保护。前缀本身含公司形状时也不剥离，不能连剥两次改变身份。
4. 两个 live run 没有 `continuous-episode.json`，但有真实 `trace.jsonl` 调用台账。旧模型准入只看 Episode 等产物，无法接受这条真实写入路径；配置和 `report.json` 的 `model` 又不是响应证据。`89527d47c` 增加具名 `llm_call_ledger` 解码、逐尝试响应身份核验、累计快照去重、JSON 字符串里的子分支引用追踪，以及真实 `_post_chat()` → `LLMCallLedger` → `RunStore.append_step()` 回归。
5. 在 `89527d47c` 的本机完整门禁运行期间继续核目录入口，发现正常 sibling Episode 会让 trace-only 子分支身份/未知调用被跳过。新增两条入口回归先红，分别要求未知调用 exit 2、错模型 exit 1；终止约 55% 的旧门禁，不能把中断日志当完整收据。
6. `b5c3d4fa8` 补 `has_branch_evidence`：trace 内的实际身份、未报告身份、未知分支调用或错误都必须纳入目录检查，不能被旁边的正常 Episode 遮住。纯普通 trace 不制造第二份空模型证据；显式点查它仍应返回无证据。
7. 提交后在干净 b5 上跑两组变异（故意破坏实现，确认指定回归变红），各 8/8 捕获；恢复后树干净。9 个冻结输入重放、两份旧 trace 身份准入均绑定 b5 和源码/输入哈希，没有检索、生成或模型判官调用。
8. b5 的第一次后台门禁启动未留下有效进程/收据，不算执行成功；后用前台命令完成全量，并显式核收据。另一工作树的 `model-first-harness-1006` 门禁属于另一任务，未借用其结果。
9. 2026-10-06 03:2x（+08:00）回读远端：PR #52 head 与 b5 全等，五项检查全部 SUCCESS。本文后续是文档提交；**文档 tip 的检查不能冒用 b5 的 revision**，后续同头收据与 CI 只追加 PR 评论，避免为记录结果再制造新头。

## 公司边界：方案对比

| 方案 | 评价 | 结果 |
|---|---|---|
| 在名字内部找任意“中/为/的/和/及”后缀 | 同字出现在真实名称内部时会改变实体身份 | 否决 |
| 全局公司白名单，或借答案里其他 claim 的证据 | 当前句没有绑定也会被放过 | 否决 |
| 惰性提取，到第一个“集团/证券”等就停 | 把更长的新名字截成较短的已知名字 | 否决 |
| 贪婪提取 + 后缀后的显式列表连接词 | 保留复合后缀，同时分别检查明确列出的相邻公司 | 采用 |
| 只恢复开头完整上下文，在当前绑定证据内核完整边界 | 修复已证实误报，同时拒绝内部切字、双重剥离、借邻句来源 | 采用 |
| 引入结构化实体表/通用中文实体识别 | 当前 claim/atom 没有这样的字段，不能假装已有；属另一个合同改动 | 本轮不做 |

实现落在 `intelligence/services/answer_model.py`；真实消费者回归在 `intelligence/tests/test_grounded_company_context.py` 与 `test_general_harness_false_positives.py`。这是有限上下文恢复，不是通用公司识别器，也没有全面重写旧 `_company_is_known` 语义。保留证据外数字、非事实升级为 fact、无绑定正文等拒收规则，不以字数保留率作验收目标。

## 模型准入：方案对比

| 方案 | 评价 | 结果 |
|---|---|---|
| 用配置、`model`、`requested_model` 或可读摘要证明模型 | 只能证明请求意图；路由、重试或服务端可返回别的模型 | 否决 |
| 全局递归寻找任意 `reported_model` | 普通报告和无关字段可伪装成真实调用证据 | 否决；trace 只消费具名台账 |
| 把失败记录/默认 `not_called` 当未调用 | provider 已尝试但未带回身份时，会丢失缺证 | 否决 |
| 每条尝试读取 `reported_model`，校验状态与冲突 | 失败但带有效响应身份也可证明模型；无身份尝试记 `unreported` | 采用 |
| 累计快照最后一条覆盖同 ID | 后面的好记录可抹掉早期错配 | 否决；仅同 `attempt_id` 且全记录相等时去重 |
| 目录找到 Episode 就不看 trace | 会隐藏 trace-only 子分支错配和未知调用 | 否决；按实际证据发现所有相关产物 |
| 保留错配优先，坏台账/身份矛盾/未知调用阻塞 | 既不会用坏记录盖错模型，也不会用好记录盖缺证 | 采用 |

`_trace_payload()` 对 JSON 编码的 `output_summary` 先解码，坏 JSON、非对象、缺名、坏 records 都拒收；子分支事件和 `episode_ref` 继续追踪。`--allow-unreported` 不是全无响应身份时的放行许可，也不豁免坏台账、冲突或未知分支调用。Episode 的 `served_model` 合同与 trace 的 `reported_model` 合同分开解释，不能套错字段。

源码/入口：`intelligence/eval/model_admission.py`、`scripts/check_model_admission.py`；回归 `intelligence/tests/test_model_admission_trace.py`；门页 `docs/agent-product-door.md`。

## 验证与收据

树外证据根：`~/.finance-runtime/pi-vs-8792-claude-review-1005/`。原始运行目录、失败日志和旧收据保留。

### 完整工程门禁：只属于 b5

```bash
bash scripts/run_main_gate.sh --pytest-args \
  "-q -p no:cacheprovider --basetemp=/tmp/pi-gate-company-admission-b5c3d4fa8"
/Users/a77/finance-workspace-private/.venv-workbench/bin/python \
  scripts/check_test_receipt.py \
  /Users/a77/.finance-runtime/test-receipts/gate-rPmLghqp/pytest.json \
  --require-full-scope \
  --require-target /Users/a77/finance-workspace-private/.claude/worktrees/8792-pi-performance-analysis-a3001e \
  --expect-revision b5c3d4fa8544f489b024dd78aae9cf93119b4334
```

- Ruff 全仓通过；pytest **20602 passed / 77 skipped / 2 xfailed / 0 failed / 0 error**，collected **20681**，948.52 秒，门禁 exit 0。
- 收据 `~/.finance-runtime/test-receipts/gate-rPmLghqp/pytest.json`：revision=b5、dirty=false、target=当前仓根、解释器为项目 venv、依赖指纹 `e1c50cb821a30f00`、依赖门禁未绕过。checker exit 0，未收窄、收执对账相等。
- 原始日志 `gate-company-admission-b5c3d4fa8.log`；核验日志 `receipt-company-admission-b5c3d4fa8-check.log`。本次指定 basetemp 由门禁绿后自动清理，不涉及真实 worktree。
- b5 GitHub [workbench-check](https://github.com/moscrol/finance/actions/runs/37359273476) 与 [registry-check](https://github.com/moscrol/finance/actions/runs/37359273760) 完成；`python`、`frontend`、`e2e`、`registry-check`、`workbench-check` 均 SUCCESS，保存 `pr52-b5-checks.json`。本轮本机全量是 Python，不冒称另跑过本机前端四连。
- 旧 `89527d47c` 本机门禁因新发现中断，没有有效最终收据；旧 GitHub run `37358252269` 另有 `test_late_malformed_final_rejudge_remains_fail_closed` 失败（assert 1 == 3，1F/20509P）。日志 `ci-895-failed.log`。b5 新运行通过**不能证明该旧失败已归因或被 trace 修复治好**；未为它修改判官实现或重采模型。

### 变异与冻结重放

| 证据 | b5 结果 | 能证明什么 |
|---|---|---|
| `company-context-mutation-b5c3d4fa8.json` | 基线38P，8/8 killed，恢复成功 | 公司恢复边界的指定错误可被真实消费者测试捕获 |
| `admission-trace-mutation-b5c3d4fa8.json` | 基线49P，8/8 killed，恢复成功 | 请求名冒充、冲突、JSON子引用、累计覆盖、sibling漏发现、未知调用均有反证 |
| `replay-company-b5c3d4fa8.json` | 旧7稿+2个live原件；源码前后相同，model_calls=0 | 量具在固定输入上的行为，不是新生成质量 |
| `admission-live-b5c3d4fa8.json` | 两run admitted，exit0；源码/trace哈希绑定，inputs_unchanged=true | 响应身份符合预期，不是内容、检索环境或运行成功验收 |

冻结重放仍通过已入库的 `scripts/review_probes/replay_grounded_validation.py`，只在内存中显式把历史 `company_scope=""` 归一化为 `"-"` 并记账，原件和生产输入合同不改。旧 run `171701_630703` 的错误数7→6、保留字符1416→1593；其余旧稿没有下降。D4旧候选仍1747字、2条确定性错误，并非全通过。

### 两份 live 原件的最终边界

共同路径：证据根下 `binding-live/users/pi-binding-1005/runs/`。

| run | 台账响应身份 | b5 原稿重放仍报的错误 |
|---|---|---|
| `run_20261005_234226_342740`（D4） | `glm-5.3-flash` ×2 | 第2句把非事实 claim 升 fact；第6句证据外数字 `4` |
| `run_20261005_235746_803448`（D1v23） | `glm-5.3-flash` ×1 | 存在未绑定 claim/EvidenceAtom 的正文；第5句证据外数字 `4200` |

这些是旧首稿在 b5 上的重放，不是 b5 重新端到端生成。两稿当时 `ASK_SEMANTIC_JUDGE=off`，属于 `deterministic_only`（只有确定性校验），没有独立第二模型审核。公司误报消失不代表答案可交付，历史错名、重复计数和“资金扩散”一类推断也不由本轮机械校验签字。

隔离旁路 `/api/readiness` 曾 HTTP503、`missing_critical=["rag_query_protocol"]`，检索增强生成的 RAG worker 关闭，market snapshot served date 为 2026-09-30 而非题设日。入口烟测能证明请求/产物链路走过，**不能冒充生产等价环境**。每题每端 n=1 不能推出性能、稳定性或总体优劣。

## 后续与不要做的事

1. 文档提交后核最新 head/Actions；如再跑本机完整门禁，必须为那个精确 revision 留新收据，结果追加 PR 评论，不改签 b5 收据。
2. 等用户统一决定合并；合入和部署仍分开授权。生产 8792、真实工作树、原始证据均保留。
3. 质量返修先对原稿、绑定证据和最终消息定位首错，保持数字、公司身份、claim type 和来源资格的拒收边界；不继续放宽校验器换绿。
4. 本轮停止模型采样。未来新质量实验须先冻结题面、模型、代码、RAG/judge状态、样本量、预算与停止规则，且与旧n=1、重放结果分账。
5. #51 合入前不启动其 invocation directory 后续任务；#49 合入前不处理依赖后续，#53 不提前改 base。任务板原有质量/发布状态不关闭。
6. 03:18磁盘约21GiB可用、96%使用率；之后重门禁前重新查磁盘与其他agent进程，不清理真实树和失败证据。

## 工具沉淀盘点

- 重复重放已归 `replay_grounded_validation.py`，不再依赖临时脚本；本轮模型身份复核使用正式 `check_model_admission.py`，没有新增只存在 `/tmp` 的准入入口。
- 发现的公司边界、累计台账和目录发现漏洞已补产品回归与提交后的变异，不只写经验文字。
- 通用原则沿用“缺失保留未知态、校验落在实际消费边界”与“门禁只证明其真正读到的证据”；本轮将原则具体落实到**真实写入器→目录发现→解析→判定**，不另造重复框架或方法卡。
- `harness-reference` 在本轮事实检查中是旧底且有他人未提交改动，未编辑它。有限中文语义边界仍需人工分析，但已确认的反例都进测试，不把语义判断伪装成通用实体识别保证。
