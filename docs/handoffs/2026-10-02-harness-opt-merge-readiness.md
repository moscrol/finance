# harness 本地推进与合入条件复核（2026-10-02）

本轮接续用户的「推进」：修复 PR #10 的四个已复现问题，检查新推分支 PR #14，补齐 Mac 全量测试。没有合 main、部署、调用真实模型、修改共享解释器依赖、写预测台账或改动另一个 agent 的实验树。

主工作树 `/tmp/harness-opt`，原有空文件 `30` 保留。解释器始终为 `~/finance-workspace-private/.venv-workbench/bin/python`。PR 修复、审查树置于主工作树的忽略目录 `tmp/` 下。所有原始日志在 `tmp/local-agent-validation-1002/`。

## 1. 固定版本与交付关系

| 对象 | 固定版本 / 状态 |
|---|---|
| 原始 19 补丁 | `fb03e8e37`，原始 tree 已核对为 `d94cedf89ba915c649ef045a19be6a808c6a3554` |
| harness 本地续修 | 代码 `2d1fb9cf8`，本轮全量受验 HEAD `cc953e16b`；与代码提交之间只有验收文档 |
| PR #10 | `arena/01a0f120-finance` / `0eb1af362`，本轮没有覆盖它 |
| 新修复 PR #15 | `codex/pr10-gates-1002` / `41c80c0c2`，base 为 PR #10 分支，保持 draft |
| PR #14 新增段 | `e7e885070...d22fb60d7` 已审；再审代码 `f4c9a5dc6`；远端随后到 `a5e0173a3`，仅追加 3 份文档 |

[PR #15](https://github.com/moscrol/finance/pull/15) 包含 `48fef0749`（四项修复）和 `41c80c0c2`（启动前存储失败的零调用边界）。推送前用现有 Gitea API/Keychain 路径只读检查，`push_mirror_count=0`；没有复制或输出凭据。推送为普通新分支推送，没有 force push。

## 2. PR #10 四个缺口及回归

| 缺口 | 修后行为 | 验证 |
|---|---|---|
| 子 worker 已保存模型响应后抛异常，父事件占位 `llm_calls=0` 被视为没调用 | `llm_calls_known=False` 明示未知；准入从子存证补证，缺证据拒绝；兼容旧异常产物 | 真实协调器驱动：错模型、正确模型、无存证、未提供 store；另测启动前取消 |
| `--trust-self-reported-admission` 让无产物运行得到正式结论 | 删除正式入口旁路；无 artifact 一律 unverified；旧参数拒绝 | CLI 无产物拒绝旁路，带本地合成 artifact 的正式分析仍能通过 |
| Mac 快照只复制数据库主文件、漏 WAL | 使用仓库唯一原语 `clone_to_staging`，携带 WAL；快照失败不读活库 | 真 DuckDB：CHECKPOINT 后 INSERT，已提交事务只在 WAL，副本仍读到该行；失败路径不回退且清理副本 |
| Ruff 失败而 pytest 成功时汇总 exit 0 | 汇总两个退出码，任一失败或超时均不为 0；保留两份结果 | 成功、失败、超时组合 |

先加入回归，旧代码 **10 failed / 68 passed**，日志 `pr10-regression-red.log`。首轮修复后 **175 passed**。独立 Spec 审查发现父 Episode 在写 branch_started 失败前从未启动 worker，却被旧格式兼容逻辑误拦；新增真实 GLMAgentRuntime/ObservedStore 用例先 **1 failed**，修正事件的已知零调用标记和旧事件区分后，8 文件 **176 passed / 7.02s**。

相关测试命令：

```bash
P=~/finance-workspace-private/.venv-workbench/bin/python
$P -m pytest -q -p no:cacheprovider \
  tests/test_model_admission_branches.py tests/test_mac_pr10_checks.py \
  intelligence/tests/test_model_harness_2x2.py intelligence/tests/test_model_admission.py \
  intelligence/tests/test_served_model_receipt.py intelligence/tests/test_sub_research.py \
  intelligence/tests/test_sub_research_persistence.py intelligence/tests/test_sub_research_tool.py
```

Standards 轴 0 条未关闭问题；Spec 轴最初 1 条边界问题已关闭。独立复跑收据为修复树 `tmp/spec-pr10-final-receipts/20261001T183233Z-41c80c0c-90bbabe7ed2c.json`（1 passed）。全仓 Ruff、提交钩子及 registry 的五项本地检查通过。注册表检查如实报告外部知识仓未在新树内，未将跳过的跨仓项冒充已验证。

GitHub `41c80c0c2` 的 python/frontend/e2e/registry-check/workbench-check 五项 SUCCESS，Python 叶运行 23m58s；受验 head 与提交逐字一致。PR 仍为 draft，base 仍为 PR #10 分支。

## 3. Mac 全量测试与临时目录纠正

首轮将 `--basetemp` 放在 Git 工作树内部，造成隔离测试向上识别了真实父仓库。`cc953e16b` 完整读数为 **19033 passed / 8 failed / 77 skipped / 2 xfailed，1101.87s**，收集 **19120**，收据 `~/.finance-runtime/test-receipts/20261001T183653Z-cc953e16-0e370566161b.json`。收据通过 full-scope 校验只说明范围和版本成立，不表示测试通过。

失败项完整保留：

```text
intelligence/tests/test_agent_review_worker.py::test_fallback_provider_failure_enters_its_own_backoff
intelligence/tests/test_market_db_path.py::test_db_follows_the_data_root_not_the_code_root
tests/test_code_map.py::test_nodes_without_git_is_error
tests/test_code_map.py::test_build_without_git_refuses
tests/test_deploy_workbench_runtime.py::test_valid_standalone_target_reaches_intercepted_sync
tests/test_main_gate_receipt.py::test_inprocess_nested_pytest_keeps_outer_receipt[outer-failure]
tests/test_pi_review_repair.py::test_real_author_checks_execute_in_sandbox[C7-spec]
tests/test_pi_review_repair.py::test_real_author_checks_execute_in_sandbox[C7-quality]
```

改回 pytest 默认临时目录，未改代码，8 项 **8 passed / 44.55s**；收据 `20261001T183840Z-cc953e16-7b3a411bdecd.json`。另把第一项单独放回仓内 basetemp，再次得到相同 `PROVISIONAL_WRITTEN != FALLBACK_INACTIVE` 失败（`fallback-inside-control.log`），确认目录设置可触发它。

两树随后均按任务书的正常命令重跑完整套件，不加任何目标过滤：

```bash
~/finance-workspace-private/.venv-workbench/bin/python -m pytest -q -p no:cacheprovider
```

完整原始末行：

```text
# harness @ cc953e16bf3aae5c4723b3d1c6d396f5839109a8
19041 passed, 77 skipped, 2 xfailed, 17 warnings in 1333.91s (0:22:13)
# PR15 @ 41c80c0c2700bc5de9a986ddee9aba12a2c03d19
18989 passed, 77 skipped, 2 xfailed, 17 warnings in 1251.94s (0:20:51)
```

两份均 exit 0。`scripts/check_test_receipt.py --require-full-scope --expect-revision <各自完整SHA>` 均通过：

| 受验树 | 官方收据（目录 `~/.finance-runtime/test-receipts/`） | 收集面核对 |
|---|---|---|
| harness | `20261001T190108Z-cc953e16-8852e86b6a6b.json` | collected=19120，与全部读数对账；无过滤 |
| PR15 | `20261001T185946Z-41c80c0c-e64d83c58e26.json` | collected=19068，与全部读数对账；无过滤 |

校验日志为 `harness-full-receipt-final.log`、`pr10-full-receipt-final.log`；完整输出为 `full-gate-cc953e16b-isolated.log`、`pr10-full-gate-41c80c0c2-isolated.log`。harness 收据中的唯一额外未跟踪文件为原有空文件 `30`；修复树干净。修复树先前两次主动中断的运行仅为过程日志，不作为全量结果。报告/交接随后仅改文档，受验代码没有再改。

本轮自己生成的四个仓内 basetemp 已删除；正常全量的临时目录按运行时保存的 inode、设备号和 PID 核对：pytest-85 确认进程结束后删除，pytest-86 已不存在。其它进程和其它临时目录未动；收据、失败记录、日志保留。清理记录 `test-directory-cleanup.json`。

环境边界：workspace doctor 检出共享 httpx 为 0.25.2、lock 为 0.28.1；本机 Node 为 26，GitHub CI 为 22。本轮未改共享环境。测试通过与环境完全一致是两种结论，不能互换。

## 4. PR #10 Mac 实库只读核验

运行 `mac_pr10_checks.py`（全量 pytest 单独运行），使用真实 users 目录和主检出数据库。原始完整摘要：`pr10-mac-48fef0749/summary.md`。最终 `41c80c0c2` 对模型准入单独复跑，读数未变。

```text
换库锁平台自检：exit 0；写者/换库锁两个方向均互斥
百分数字段量纲：exit 0；快照 method=clonefile，结束后删除
标签 A/B：966 存证 / 14 还原失败 / 952 可回放
涉及 568 卡 / 158 runs；待核 325→325；消失 0 / 新增 0
模型准入（20260916 以来57 runs，统一期望 glm-5.3-flash）：
  admitted 46 / mismatch 6 / no_evidence 5；exit 1
  未补证子分支 3；默认 episode store 不存在，未用
记忆召回、工具审计、台账体检：各步骤 exit 0
```

以上 A/B 脚本的 exit 0 不能解释为全部 966 份有效：14 个错误仍存在，其中 11 个 `required_outputs 必须是 list`、3 个 `invalid claim source bindings`。#11 已另行改造严格门禁并兼容其中 3 份；本次没有覆盖其实现。此次模型准入抽查是混合历史运行对同一期望模型的核对，不能把其中其它模型运行一概宣称为模型网关错误。

量纲结果（字段值 / 同日原值反算的百分数）：

| 字段 | 有效比值配对 | ≈1 占比 | 判定 |
|---|---:|---:|---|
| 复盘会竞价 auction_pct | 7749 | 99.69% | percent |
| 同表 pct_chg 对照 | 9474 | 99.17% | percent |
| 同花顺竞价 auction_pct | 10889 | 100% | percent |
| 海外个股 pct_chg_5d | 71189 | 76.19% | unclear，低于80%门槛，未改标签 |
| 海外个股 pct_chg 对照 | 62254 | 95.18% | percent |

召回标注集仅 15 题，T0/T1/T2/T3 hit@5 分别 0/1/3/3，不能据此宣称通用语义召回收益；未安装或运行语义模型。工具审计、台账体检均只读。台账读数来自本候选分支自己的文档版本，不能冒充其它分支或生产的最新台账。

## 5. 新推 PR #14：旧增量通过，最新候选有 1 个 P2

固定 `e7e885070...d22fb60d7`：7fe24b0f5 修正历史主线窗口/截止日表达；80e4f149a 区分工程正确和完整行为失败；d22fb60d7 回写通用 harness 放大模型的目标、撤回固定全句检查方案。

Standards 轴 **0 个可操作问题**；Spec 轴 **0 个可操作问题**。独立 DuckDB 内存夹具 11 个 assert 通过；正式新增测试文件 `intelligence/tests/test_mainline_history_scope.py` **12 passed / 1.16s**。收据 `~/.finance-runtime/test-receipts/20261001T182807Z-d22fb60d-fc8559c1d3f7.json` 已按精确 revision 校验。

GitHub `d22fb60d7` 的 python/frontend/e2e/registry-check/workbench-check 五项 SUCCESS。文档仍明确 **whole-task 0/4、改善 refuted**；焦点两案通过仅是诊断。没有把 CI 或局部测试绿灯解释成金融回答能力已经改善。

随后 PR #14 推送 `f4c9a5dc66bf4a09c27b18dc29b0714a49087c03`，10 文件新增 opt-in `evidence_read`：模型可以补读本 Episode 已交付证据的 title/detail。默认关闭，须开关和显式能力授权；没有扩大数据源或日期范围。本地四文件检查：

```text
65 passed in 2.00s
```

测试为 `test_evidence_read.py`、`test_research_progress.py`、`test_tool_result_budget.py`、`test_mainline_history_scope.py`。收据 `20261001T190113Z-f4c9a5dc-9d7a0854483d.json` 已按精确 SHA 校验；这是定向测试，不是新候选全仓绿灯。

本次 Standards 轴 **0 个可操作问题**，Spec 轴发现 **1 个 P2（未修）**：

> **子任务已交付正文的重复读取被算为新进展。** 新增 `agent_episode.py:943–952` 只在普通工具返回时记录已展示覆盖；计划分支的 `_append_sub_research_message:3468–3477` 将完整材料送入模型，却未播种同一覆盖账。开关 on + 显式授权时，一份 900 字分支原文已经完整出现在第 2 次模型请求；再调用 `evidence_read(E1, offset=239, limit=100)`，后续预算消息仍给出 `new_read_chars=100, new_evidence=0, stalled_batches=0`。按“重复页/重叠页均去重”的规格，应为 `new_read_chars=0`；错误读数可能让启用停滞收口的运行继续消耗预算。应在分支回灌实际被认领进 messages 后登记已展示范围，不能在 worker 完成但尚未交付时提前登记。

独立零模型原生 Episode 复现通过两条确认断言，使用 ScriptedModel 和 StubCoordinator，产品源码没有改动。默认关闭的候选仍保留原样；不把这次工程复现当作模型收益评估。复现脚本为 `tmp/local-agent-validation-1002/pr14-evidence-read-sub-research-repro.py`，stdout 为同目录 `pr14-evidence-read-sub-research-repro.stdout.txt`。在 f4 的独立检出根运行脚本即可复核（脚本从 cwd 导入受审代码）。原始摘要：

```json
{"full_original_already_visible_chars":900,"expected_new_read_chars":0,"actual_new_read_chars":100,"new_evidence":0,"stalled_batches":0,"real_model_calls":0}
```

干净的 detached 审查树完成后已用 `git worktree remove` 移除，复现和证据留在主工作树忽略目录；PR15 未合分支及工作树继续保留。复现是固定版本的审查证据，尚不是产品回归；后续修复该问题时应把期望值改为 0 并迁入正式测试。

远端随后到 `a5e0173a367945b2b4d248ec4656f4e999bf7387`，GitHub compare 确认仅 3 份实验/台账/交接文档，运行时代码仍是 f4。文档保留另一 agent 的 401 失败批次为 inconclusive，后续另起批次；本地只读这些记录，没有接管实验、调用模型或写台账。截至本轮抓取，a5 的 frontend/e2e/registry SUCCESS，python IN_PROGRESS，workbench 尚无完成结论；旧 d22 的成功不能覆盖新候选。原始 API 快照 `pr14-current-ci.json`，文档差异 `pr14-f4-a5-delta.json`。

## 6. 合入阻断与下一步

本轮只读合并预演没有修改工作树或开启真实 merge：

- PR #11 从 `983590438` 分出，后续 PR #10 的 bcd8a470f、45d9a6e70、0eb1af362 与它不是直线历史。`git merge-tree` 与 GitHub 均确认冲突；GitHub #11 `CONFLICTING / DIRTY`。
- 五个冲突文件：预注册文档、质检报告、`intelligence/eval/model_admission.py`、`scripts/check_model_admission.py`、`scripts/model_harness_2x2.py`。#15 与 #11 的模型修复有重叠，整合须保留 #11 的递归取证和 A/B 完整性规则，不能盲目依次合。#15 与新代码 f4 再预演仍为这 5 个冲突，日志 `pr15-pr14-f4-integration-preview.txt`。
- 原始 harness 19 补丁与 #14/d22 预演有 14 个冲突文件；本地续修 `cc953e16b` 与新代码 f4 再预演仍有 14 个，详见 `harness-current-pr14-f4-integration-preview.txt`。应按原任务书 §6 拆批次去重；不能拿分支各自绿灯证明合并树通过。
- 准入接口也已分化：#10/#15 使用单个 `artifact`、`episode_store`；#11 链使用 `artifacts` 列表、`episode_store_roots` 和逐文件哈希。后续统一接口时必须联动对应测试，不能只在冲突中选择 ours/theirs。

本轮已询问 2×2 是否收口，尚未收到确认；按任务书 §6 暂不进入合入流程。仍等待冻结 A7 决定、23家/42家两句未来条件的严格数值验收边界。工具差分分支、Gitea 清枝、曝光凭据轮换、预测台账写入继续只汇报、不处理。

已有真实 KB 探针和数值重放结论不重写：anchor=16，一致率0.889；966份/955还原/11失败；相对main释放15个数，13个事实复述、2个未来条件需人工判断。内容正确性仅selftest，完整模型评测等待实验结束。原文、逐条证据及全部剩余路由差异见 `2026-10-02-harness-opt-local-followup.md`。

## 7. 决策记录

| 采用 | 被否方案 | 理由 |
|---|---|---|
| PR #15 独立草稿、base PR #10 | 直接覆盖 #10 或合 main | 保留他人正在推进的分支，先让补丁可审阅 |
| 明示未知调用账并读真实存证 | 用占位0证明未调用 | worker 异常会丢失返回账，不能伪造历史事实 |
| 正式入口删除自报旁路 | 仅加警告而仍给正式结论 | 预注册要求产物证据，警告不能实现硬门 |
| 复用快照原语、失败停止该步 | cp主文件或失败读活库 | 避免漏掉已提交 WAL 事务及混用读数来源 |
| 默认 pytest 临时目录重跑 | 修改产品代码适配仓内测试夹具 | 失败由测试隔离环境触发，产品改动不能修复错误量具 |
| 报告分支重叠与冲突 | 把 PR14 绿灯当整个链可合 | 当前 CI 未验证各分叉汇合后的树 |

工具沉淀：四个缺口已落在现有门禁及回归测试中；没有新增临时专用命令取代正式脚本。合并预演与原始结果保留在本任务日志中。用户限定本轮工作目录，因此没有写共享记忆库或其它仓库。


## 8. 原任务书逐节状态

| 原任务书节号 | 状态 | 当前有效结果 / 原始证据 |
|---|---|---|
| 1 补丁 | ✅ 已完成并核树 | fb03 的指定 tree 一致；19 个提交原始清单见 `2026-10-02-harness-opt-local-validation.md` §0–1 |
| 2 Mac 测试 | ✅ 已补齐全量 | harness 19041 passed / 0 failed；本报告 §3 含原始末行和 full-scope 收据 |
| 3 真实 KB 探针 | ✅ 达门槛，差异保留 | anchor 三轮均16；consistency .622→.822→.889；clarify 3→0→0；llm_fallback 均0；各风格及5条全部 mismatches 原样见 `2026-10-02-harness-opt-local-followup.md` §3 |
| 4 数值 A/B | ❌ 严格人工门未全过 | 966/955还原/11失败；相对main消失15/新增0，其中13正确复述、23家/42家两句未来条件未签通过；异常原句、证据、差异两栏见同文 §4 和首轮报告 §4 |
| 5 内容正确性 | ✅ selftest；跳过完整答卷 | 实验未确认结束，不占模型配额；原输出见续修报告 §5 |
| 6 实验后合入 | 跳过（等待确认） | 已有 draft PR15；没有合 main；已查镜像方向，已列出链间冲突 |
| 7 用户决定 | 仅汇报 | A7、工具差分分支、Gitea 清枝、曝光凭据轮换、台账写入均未代决 |

本报告更新“全量未跑”和“PR10四项未修”的历史状态；先前日期报告保留当时事实，不覆写失败证据。
