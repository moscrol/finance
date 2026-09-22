# 市场—板块—个股历史过程研究：收口接手入口

## 这个分支做什么
把 #845（forward-boundary）与失散的历史证据绑定补丁链合到一处，补齐四道真题暴露的
能力缺口，并把「模型做对了系统能不能让它交出去」这件事变成可重复的测试。

树 `/Users/a77/fwp-wt-history-completion-0922`，分支 `fix/history-completion-0922`，
基线 `gitea/main@a2c8d1f90` + merge `442476f7d`。解释器
`/Users/a77/finance-workspace-private/.venv-workbench/bin/python`。

## 当前状态（2026-09-22）
四个提交，自下而上：

| 提交 | 内容 |
| --- | --- |
| `101678e89` | 合并 #845 与证据绑定链；补回缺失前置 `3765af67b`（跨页保留源行坐标），逐 hunk 合双方意图，34 条失败清零，未削弱任何测试 |
| `613376089` | `compare_cases` 规则型条件：控制组能力（本轮主要业务缺口） |
| `4e000ee22` | 两处「历史算子清单」补齐为引擎声明的六个（BLOCK 级死路） |
| `c1d4643df` | 引错算子按剔除处理而非整格作废；四题离线干跑 |
| `7fc60d279` | 「本轮欠不欠一份条件全集比较」改为逐轮判据（下一节） |
| `0ee839f14` | 四题四种形状全部离线走通（8 条） |

## 门禁收据（干净树）
`.venv-workbench/bin/python -m pytest -q -p no:randomly`，收据
`~/.finance-runtime/test-receipts/20260922T141005Z-0ee839f1.json`：
revision `0ee839f1492afdc95d7aa1fd65770cc94a0a1afc`、`dirty: false`、
**12984 passed / 1 failed / 89 skipped / 2 xfailed**、`exit_status: 1`，日志
`~/.finance-runtime/reviews/history-completion-20260922/full-final.txt`。
（上一轮 `c1d4643df` 的收据是 `20260922T125353Z-c1d4643d.json`，12975 passed / 1 failed，
同一条失败。）

唯一失败 `tests/test_code_map.py::test_structure_probe_daily_full`：断言为
`assert 'market_feature_store' in '[]'`——`code_map.py query` 的结构层在
`search_graph` 取不到结果时会给 `unavailable` 并返回空命中，而这条用例只断言命中内容。
两次全量都在本机同时跑着别的 agent 的全量（`~/.finance-runtime/test-receipts/` 里同
时间段有 b4a35fa2、a945c51f、d68b8f51 等别的 revision），本树的 `graph.db` 有 542MB，
磁盘还剩 4%。单跑 `tests/test_code_map.py` 42 passed / 3 skipped。不属本次改动面，
不移签为绿，也不改它去容忍失败：收据原样留着。

ruff：`intelligence tests` 全绿。历史域受影响面（-k 筛选）：最后一次 2050 passed / 9 skipped；
含 episode/harness/research/decision 的更大切面 3418 passed / 2 skipped。

## 四个缺口的收口情况
1. **控制组**（第四题）——**已实现**。`compare_cases` 的 X 原来只能是「某数值过线」，
   表达不了「当时是否启动」，未启动样本无处安放。现在支持 `{"rule": "launch_signal"}`：
   判定沿用 `trace_history` 同一套规则（`anatomy.launch_state()` 单一出处），x=true 启动、
   x=false 控制组、x=null 不可判定（缺数/历史不足，留在 `enumerated` 分母，
   `comparison.launch_states` 分状态计数）。规则名与版本进 `feature_definitions` /
   `definition_refs` / `selection_fingerprint`，随原件走。测试
   `tests/test_history_launch_control.py`（10 条）。
2. **同窗排名**（第二题）——**已可交付**，见 `tests/test_history_four_question_dry_run.py`
   第一条：同一参照窗口内做全市场板块排名、板块成员股票排名、代表板块启动路径，三份原件
   同起止日期、同 `source_query_id`，两种排名各自成件，且真实绑进正文。
3. **启动时特征**（第二、四题）——由 `trace_history` 的 `launch_signal` 行提供同口径特征，
   `compare_cases` 现在用同一条规则打标签，两边不会各说各话（`test_history_launch_control.py`
   里有与 `trace_history` 同日期同结论的一致性断言）。
4. **原件到正文**（全部四题）——证据绑定链已并入：每张 model card 指回一行不可变查询行
   （`row_index` / `row_identity` / `row_hash` / `observations`），终局校验 `_valid_history_identity`
   逐条核对卡面与内容是否一致。

## 本轮查出的真问题（都不是模型的错）
1. **两处「历史算子清单」停在四个**，漏掉 `rank_history` / `trace_history`：
   `episode_factory` 的槽位白名单与 `agent_research.HistoricalEvidenceProvenance.validate()`。
   后者与槽位无关——任何 trace/rank 证据卡一律「身份无效」。第二题要区分全市场排名与板块
   成员排名并追踪代表，第三题要验证接力，只能由这两个算子产出：模型一步不错，终局也会吃
   `history_operation_unsupported`（BLOCK）。**原验收第二、三题的失败正落在这个形状上。**
2. **引错算子整格作废**。同一文件早有教训（2026-08-19 `run_20260819_130854`：混绑导致整篇
   退成缺口模板）后改成「剔除非法、保留合法」，救回的历史白名单没沿用。已按同口径改。
3. **四道真题全部被判 `comparison_analog`**，槽位相同（`docs` 无此记录，实测得出）。
   这意味着每轮都要求 `analog_similarities` 这类只认 `find_analogues` 的格子。

## 第四处真问题：该问「这一轮」，不是问「这段对话」（已改，`7fc60d279`）
`assess_history_finish` 判「本轮欠不欠一份条件全集比较」时读的是对话级
`intent.purpose`，而 purpose 在跟问里继承。实测 Q1..Q4 全是 `historical_comparison`，
于是第二题（当时谁走强）、第三题（有没有别的板块接上）**无论答得多好都被强制降为
partial**，通知说「尚未完成声明条件全集的历史比较」——用户这两轮没要过规律。
这是真实验收「四轮 transport completed 但 report 均 partial」的最后一段。

改法：`HistoryIntent` 新增逐轮字段 `comparison_requested`（None = 未判定），
`requires_full_comparison` 属性回落到 purpose，所以旧原件、旧调用方、直接构造的 intent
行为一字不变；推断与跟问继承时按本轮原话重新判（权限仍然继承，只有这一条逐轮）。
实测四题得 `[False, False, False, True]`——只有第四题说了「如果要说有后续收益规律，
请把未启动或失败样本…也纳入比较」。提示词同步：不要求样本全集的回合明说不必另起
`compare_cases` 凑比较（省下的是只有 5 次的工具预算）。

为什么这不是放水：
- 词表刻意窄，不收「胜率」——它在真实提问里几乎总以否定形出现（第一题就是「不要把
  相似程度当预测胜率」），收了会把警告读成请求。
- 漏判有兜底：模型若声明 `claim_level=historical_comparison` 却没引 `compare_cases` 原件，
  `history_missing_comparison` 仍直接 SUBSTANCE 拒收。本条只管「用户这一轮有没有要」。
- 被钉住的意图没动：`test_partial_comparison_cannot_be_upgraded_by_omitting_optional_envelope`
  直接构造 purpose=historical_comparison 的 intent，回落后仍 force_partial，原样通过。

## 离线四题干跑（`tests/test_history_four_question_dry_run.py`）4 形状 × 2 循环
让脚本化「满分模型」按四题形状把事做对，证明交付通路存在，用来把「模型没做对」与
「系统不让它交」分开。四条分别对着四个真实失败点，均 `completed`、无 BLOCK。
没走真模型、数据是合成的：**这不是业务验收**。

沿途钉住的两条约束（易被忽略）：同一轮里 trace 的观察终点必须唯一
（`history_window_observation_conflict`，否则可给每个实体各挑一个终点）；
「completed」要求每个证据槽都有**本轮**原件，所以跨轮讨论同一段类比时要重做一次同口径
检索，而不是拿别的算子充数。

## 下一步（接手先做）
1. **真模型四题复验尚未做，需要你授权**（付费 provider）。做法：新隔离根、新 SHA、按原题
   原窗同一会话；旧失败原件在
   `/Users/a77/fwp-wt-history-market-anatomy/docs/verification/history-market-anatomy/fbd8f2a6/`
   保留不覆盖。现场模板见 `~/.finance-runtime/history-anatomy-live-20260918-fbd8f2a6/`
   （`start.py` 断言仓库 HEAD 与 clean，隔离 `FORESIGHT_USER` / `FORESIGHT_USERS_DIR` /
   `FORESIGHT_EPISODE_STORE`，`FORESIGHT_LLM_KEYCHAIN=0`；`run.py` 顺序跑
   `scripts/workbench_probe.py`，失败即停）。复验前把 `start.py` 里的 HEAD 断言改成本分支
   提交，别改隔离参数。
2. 四题问句就是 `tests/test_history_live_seams.py` 的 `FIRST` + `FOLLOWUPS`，与验收用的是
   同一份文本，不要另抄一份。
3. 未合并、未部署、未动主工作树与生产 8792；PR 也未发。

## 决策与被否方案
- **扩展既有 `compare_cases` 而不是新建算子**：`trace_history` 已能算启动日特征，缺的是
  「用同一条规则给全体打标签」的表达力。新建算子会让两套判定漂移。
- **控制组按「当时尚未启动」定义**，不是「事后涨得差」：后者是拿结果挑输家衬托赢家，
  仍是幸存者偏差。
- **不放宽 `assess_history_finish`**（见上一节），不为让测试变绿而改判据。
- **`analog_similarities` 仍只认 `find_analogues`**：放宽是给题目真正需要的算子让路，
  不是取消作用域——相似点必须由真做过的类比检索支撑。

## 未验证 / 已知边界
- 真模型四题未跑（本轮全部是脚本化模型 + 合成数据，**不是**业务验收）。
- 干跑用的是 `anatomy_db` 合成库（25 个交易日、两个板块），不能替代真实库上的口径检验。
- `#841` 独立审查仍是 `BLOCKED_PROVIDER_QUOTA_NO_FINAL_REPORT`（provider 429）。
- 本地 Gitea API 查 PR 状态返回 403，线上 PR 状态未重新核实。

## 踩过的坑
- `rg -rn 'pat' paths`：`-r` 是 `--replace`，`n` 会被当替换串，输出里所有匹配变成 `n`。
  查代码用 `rg -n`。这一路踩了两次。
- 查「字段有没有送到模型」要看**实际发出的载荷**（`contract.to_dict()`），不要盯某处
  render 推断。我据此写错过一条注释，已在 `episode_verifier.py` 里纠正并留痕。
- 收据目录固定在 `~/.finance-runtime/test-receipts/`，`FWP_TEST_RECEIPT_DIR` 不被读；
  `latest.json` 可能属于别的分支，按 revision 前缀找。
- `_code_dirt()` 只把代码/测试/契约/配置算脏，`docs/` 不算——跑全量期间可以写文档，
  但不能碰源码。
- 本机可能有别的 agent 在并发跑测试，`test_rag_worker` 那条时序用例会抖；单跑确认。
- `tests/test_code_map.py::test_structure_probe_daily_full` 依赖本地
  `.code-review-graph/graph.db`，图不全会失败，重建后 42 passed / 3 skipped。
