# KC 批 C/D/E 合链 + 总验收 — 验收方读数

- 日期：2026-08-18
- 派单：`docs/handoffs/2026-08-18-kc-cde-final-acceptance-plan.md`（#196）
- 规程：`docs/workflows/acceptance-workflow.md`
- 主干 tip：`3af5c81f9595`；8792 已切至同一 revision
- 结论一句话：**十张全部合入并通过批次门禁；总验收四项 1 项未跑、2 项不通过、1 项未做。KC-19 门不升格。**

---

## 1. 合链（十张，全部 merged）

| 链 | PR | KC | 独立复算读数 |
|---|---|---|---|
| C | #178 | KC-05 | 追披露链到合成上下文：`counter_count==0` → `MISSING_COUNTER_EVIDENCE` → `bundle.counter_disclosure` → `ask.py:3361` 进 `gap_lines` → `"分歧反证"`。**零反方证据时不可能沉默**。定向 190 passed |
| C | #180 | KC-06 | `hop_retrieval.py` 87 行**零 LLM 引用**；`SECOND_HOP_TARGET_CAP==3` + `SECOND_HOP_EXTRACT_MAX` 双上限；确定性由 `first == second` 断言。定向 198 passed |
| C | #182 | KC-07 | **只披露不补搜：import 清单仅 `re`/`dataclasses`/`datetime` + 两个常量，无任何检索或 IO 模块，结构上不具备补搜能力**。四问各有正负样本。定向 136 passed |
| C | #183 | KC-08 | 同源计 1 / 异源计 N / presenter 标记 / 抽不出文档名不算单源，四类均有测。定向 112 passed |
| D | #184 | KC-09 | ADR 0002 三红线逐条过：写 `users/<id>/judgments.jsonl` 无第四本；`CONFIDENCE_LEVELS=("高","中","低")` 无数值概率；抽取器 `只写 pending`，`accept_judgments` 为通向 accepted 的唯一路径。定向 27 passed |
| D | #185 | KC-10 | 可机读裁决 / 不可机读入队 / **原文未动** / 空 job 幂等，四条各一测。定向 14 passed |
| D | #186 | KC-11 | `同类判断历史 {hits}/{n} 命中（分母=已裁决数）`，三态（够 N/不够 N/零裁决）齐；红线自守测试 `test_recall_count_and_confidence_are_not_win_rate`。定向 74 passed |
| E | #188 | KC-14 | 白名单 3 条源**全部带 `credibility`**（权威机构×1 / 媒体×2）；四级分级与 spec 逐字一致；别名生成器 2 测。定向 72 passed |
| E | #190 | KC-15 | 「必然跟涨」三处出现全是**禁止**措辞；`跟涨` 仅在 `_MAP_TERMS` 意图词表。定向 18 passed |
| E | #194 | KC-12 | `slots[:4]`/`items[:4]` 钉条数；`test_polish_type_change_is_dropped` 钉「LLM 改不了选题」；澄清轮在 `app.py` 走早返回不调 `generate_followups`。定向 218 passed |

### 1.1 队列结构与派单前提的偏差（重要）

**派单写的「C/D/E 三条独立链」拓扑上不成立。** 十个分支是一条**严格线性堆叠**：每张只加 1 个提交，且每张包含它下面所有张（kc05 ⊂ kc06 ⊂ … ⊂ kc12，实测 `rev-list --left-right` 左侧恒为 0）。后果：不能改序、不能单独打回中间任一张。

**基座落后主干 38 个提交**，含 #167 数据根修复 + 批 A 三张 + 批 B 四张，与本链重叠五个文件（`ask.py` / `ask_types.py` / `app.py` / `episode_tools.py` / `evidence_registry.py`）。交付方在批 A/B 验收并行期拉的分支，之后未 rebase。

### 1.2 Gitea `mergeable` 字段不可信

十张 API 均报 `mergeable=true`，实测 **#190/#194 有真冲突**（只读 `git merge-tree` 探得）。与台账记录的 patch-checker 队列故障同源。

> **后续验收 session 注意：不要拿 Gitea 的 `mergeable` 当门禁，用 `git merge-tree --write-tree` 自己探。**

冲突体：`test_evidence_registry.py` 块序表，批 B 插 `D12/D13`、KC-15 插 `D17`，改同一行。源文件 `evidence_registry.py` 自动合并已同时含两者。经用户裁决后由验收方代解（两行取并集，与源文件生效序一致），改分支不改主干，commit `5de117e7`，pre-commit 五道门禁全绿。

---

## 2. 批次门禁（四件套，main tip `3af5c81f`）

| 项 | 读数 | 基线 | 判定 |
|---|---|---|---|
| ruff | All checks passed | — | ✅ |
| pytest | **5511 passed / 12 skipped** | 5428 / 12 | ✅ 只升不降（+83） |
| webapp | lint ✅ typecheck ✅ **65 test** ✅ build ✅ | 65 test | ✅ |
| 收据树 SHA | `20260818T042851Z-3af5c81f.json` | — | ✅ == main tip |

**测试壳校准**：动工前先在 `0e7e21e6` 上复跑，得 **5428 passed / 12 skipped**，与台账门禁行逐字相同，证明 `env -i` + `umask 022` 配方可信、后续红绿可采信。

---

## 3. 8792 链切

- 目标 `3af5c81f9595`；回滚锚 `finance-workspace-4a3bb31366c2` 保留
- T+55s ready，**readiness 13/13 全 true**
- health 三读一致：`source_dirty=false`、`code_matches_repo=true`、`loaded/repo` 指纹全等、模块 576/576
- grounded 探针（长电题、`use_llm=False`、生产 env 形状）四项达标：`market_data_source=duckdb`、`snapshot_date=2026-08-17`、`data_repo_root=私有仓`、**无「本轮没有连接本地市场数据」**。收据 `~/.finance-runtime/live-probe-traceability/cutover-3af5c81f9595-20260818.json`
- 备份 `~/backups/gitea-20260818-post194.tar.gz`（1.2G）

### 3.1 规程缺陷（已修，见本 PR）

`acceptance-workflow.md` §4 链切五步**缺 `git fetch`**，直接 `rev-parse gitea/main`。而验收 session 总是刚合完 PR 才切——那一刻该仓的 `gitea/main` 必然是陈的，照抄会把 8792 钉到旧 revision。本次手工补 fetch 才切对。

---

## 4. 批 0 身份验证

| 读数 | 结果 |
|---|---|
| ① `resolve_user_id(None)` | `'linxiaoqi5111'` ✅ |
| ② run 落点 | `users/linxiaoqi5111/runs/run_20260818_123657_507335` ✅（`run.json` 的 `user` 字段亦为 `linxiaoqi5111`，身份端到端通）|
| ③ corrections | 盘上 **61** ✅（checkpoints 50 / verdicts 104，与 ADR 0002 实测节逐字相同）|

**③ 只完成一半，如实记：**「盘上有 61 条」≠「`memory_lookup` 能见到 61 条」。用于验证的 `/api/runs` 走**引擎 B**（`ask_retrieve_compose` 写死流程），trace 中 `memory_lookup` 出现 **0 次**——**这不是工具坏了，是入口不对**：ADR 0002 明写「连续对话走 `memory_lookup`」。且 pre-commit 工具可达性审计提示 `memory_lookup` 是条件装配、「生产入口若忘了传那个输入会静默永不装配」。**强形式待补，走会话路径复验。**

补充：`FORESIGHT_USER=linxiaoqi5111` 已随 2026-08-18 10:52 那次链切生效——本 session 在旧进程 PID 67921 的**进程环境**（非配置文件）实测确认，派单该判断成立。

---

## 5. spec §10 总验收四项

### ① 6 题蒸馏基准 —— **未跑（缺件阻塞，非工时）**

**六道题的逐字题面在仓内与 vault 中均无记录。** 已穷尽查证：

1. 全仓 `.md/.json/.jsonl/.py` 按四个特征短语 grep —— 四个命中（`handoff-20260709.md`、`knevo-vs-workbench-技能包对比台账.md`、`2026-08-01-three-harness-architecture.md`、`2026-08-05b-user-memory-semantic-recall.md`）**全部是叙述性引用，无题面原文**
2. `/Users/a77/agent-memory/` 全树 —— **零命中**
3. `intelligence/eval/cases/` —— 无 6 题集文件（28 题集在 `acceptance_cases.json`，另有 uq15 等，均非此集）

**不自行重构题面。** 拿自造题面产出的答案去比另一套题面产出的 Knevo 冻结记录，会得出一个看着权威但不成立的翻盘判定——正是 spec 尾节红线要防的。**回补单：先补录 6 题题面到 `intelligence/eval/cases/`，再跑。**

### ② 28 题 A/B/C 冻结集 —— **不通过**

跑法：旁路 sidecar :8796（`live.lock` 已确认不存在），加载 revision `3af5c81f9595` == 主干 == 8792；走 `acceptance.py run` 的真实点击路径 `POST /api/conversations/{id}/messages`；28/28 全跑完，trace `intelligence/eval/runs/20260818T051630Z.json`。

> 前置检查曾拦下一次：客户端 `FORESIGHT_USERS_DIR`（`~/.zshrc` 的 `agent-memory/.foresight`）与 sidecar 的 `live-probe-traceability/users` 不一致。**按提示修好再跑，未用 `--force`。**

对照 08-15 clean baseline（`20260815T1005Z-r5-clean-baseline-3.json`）逐题比：

| | 结果 |
|---|---|
| 聚合 | 通过 4 / 失败 12 / 不可判 12，可判子集 4/16 —— **与基线完全相同** |
| 回归 | **0 题**（本行原写「1 题 B7」，经 trace 分诊**已撤回**，见下）|
| 改善 | 1 题：`A6-limit-advance-ladder` 失败 → 不可判 |
| 持平 | 26 题 |
| **B1**（光刻胶）| 不可判 → 不可判 **未翻绿** |
| **C1** | 失败 → 失败 **未翻绿** |
| **C2** | 通过 → 通过 —— **08-15 基线上就已通过，不是本批翻的** |

**判定不通过**：三题零翻绿，另有一题回归。

两条不把话说死的保留：

- ~~**B7 的回归待复跑确认**~~ —— **已撤回（2026-08-18 trace 分诊，`docs/verification/2026-08-18-kc-acceptance-triage.md`）**。B7 **不是回归**：答案已正确写出两日成交额（`2.96万亿` / `2.19万亿`，与期望 `29569.03` / `21949.97` 亿相差 0.10% / 0.23%，均在 ±1% 容差内），是**判分器 `acceptance_verdict._fact_rule` 缺中文数量级单位归一**，抽裸数 `2.96` 去比 `29569.03` 必然 0 命中。实测：按万亿归一后两值均命中。该题由 08-15 的「不可判」变「失败」，方向是**产品表达变完整后撞上判官盲区**，被记反了。修法 `EVAL_ONLY`，不得据此动产品。
- **B1 的「不可判」不等于没进步**：证据绑定数从 R15 的 **0 条**升到 **21 条**，KC-06 两跳机制看得见在工作；判不了是因为 trace 缺 `agent_eval TurnInput observations`（**harness 埋点缺失，不是答得不好**）。B1/B2/B3 三题同因。

### ③ 逐 KC 收据审计 —— **不通过**

| | 结果 |
|---|---|
| 单测收据 | **18/18 全有**，202 个专项用例，全部在 main tip 门禁内跑绿 |
| live 收据 | **17/18 缺**，仅 KC-17 有（`kc17-r15-a3`，上一 session 所打）|

按派单「缺=该项验收未完成，开回补单，不许『整体感觉都过了』」，判**未完成**。

（KC-12 实有 live 证据——`run_20260818_123657_507335/followups.json`：3 条追问、角度 A/B/D 各一、`llm_used=true`、落在合同 2–4 内——但未落约定收据目录，按位置约定仍计缺。）

### ④ 新块纪律抽查 —— **未做**

D7/D9/D12/D13/D17/W7/followups 七块逐块 live 人工核，本 session 未执行。

---

## 6. KC-19 门与出口

**未见翻盘 → 批 F 维持不开**（派单裁决）。港股 KC-16 不随结果重议。

差距归因（按证据强度排）：

1. **判据侧先于产品侧**：28 题里 12 题「不可判」，其中 B1/B2/B3 因 trace 缺 `agent_eval TurnInput` 埋点、A8/C6 因题目相对时间锚不可复现。**可判子集只有 16/28**，产品真实水平被判分器上限压住。
2. **6 题基准缺题面**，唯一能回答「赶超了没有」的那把尺子当前不可用。
3. 本批十项功能单测层面全部落地且门禁 +83 测试，但**live 侧只有 1/18 有收据**，功能是否在生产路径上真的работает，证据不足。

**结论：现在没有可支撑开批 F 的翻盘证据，但也不能据此说产品没进步——两条尺子（判据埋点、6 题题面）本身有缺口。建议先修尺子再判赶超。**

---

## 7. 回补单（建议开单，按优先级）

1. **补录 6 题基准题面**到 `intelligence/eval/cases/`，附 2026-08-07 Knevo 冻结记录的对应关系 —— 阻塞 §10①，优先级最高
2. **补 `agent_eval TurnInput` 埋点**到 acceptance trace —— 直接把 B1/B2/B3 从「不可判」解锁，是提高可判子集分母的最短路径
3. **17 个 KC 的 live 收据回补**
4. ~~B7 复跑定性~~ → 改为**给判分器加单位归一后用同一份 artifact 重跑 board**（零 LLM 成本；分诊 `R-20260818-01`），并顺带扫其余 fact 失败有无同族误判
5. **`memory_lookup` 走会话路径复验**能否见到 61 条 corrections
6. **新块纪律抽查**七块
7. 修 A8/C6/C1 的题目相对时间锚（#13 已知缺陷）
