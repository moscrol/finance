# 2026-08-16 观点题 10 题冻结集

## Verdict

- outcome: FREEZE_ONLY
- live_ab_ran: false
- failure_criterion: 未开对照窗。本文件只锁题面、复用、新挖来源、假数字护栏机制和 5pp，不报告交付率或剥句率。
- pre_arm: `437cd5e9aa1ac2681ef3f990dee01866aec82b5c` @ 8794（树已重建：`~/.finance-runtime/finance-workspace-outlook-pre`；**服务未起**）
- post_arm: 开窗时 8792 生产 tip（须 ≥`773b3d7e` + 预算回归处置）
- fixture: `intelligence/eval/fixtures/outlook-ten-question-frozen-2026-08-16.questions.json`
- loader: `intelligence/eval/outlook_ten_question_frozen_set.py`
- pr: Gitea **#82**（本冻结；不是开窗许可）

## Freeze

- frozen_at: 2026-08-16T14:05:36+08:00
- fixture_sha256: `ac464158a724c6312b373b59a4bae2ebc1f81925b5c6e284e85c22547bc7d608`
- mined_from: `default` + `linxiaoqi5111` 共 540 条 `report.json`；outlook 标记题 20 个唯一题面
- reused: 长尾冻结集 outlook 档 L01–L05，题面 / as_of / source_runs 逐字不改
- predicate: 题面含「你认为 / 你觉得 / 怎么看 / 机会在哪 / 会怎么走」；来源是真实 run 的 `report.json`；**最新一次完整 report 的 `question_type` 不是 `market_forecast`**；`as_of` 与题面都不触发休市日闸
- do_not_open_until: 长尾窗 `all slots processed` 且 95 槽位齐、8793 已停（`ps -p` 验 argv，不用 `pgrep -f`）、预算回归**判断正文**修复已合或书面豁免
- not_gate_2: `#84` `21dbf6c1` 是 R-01 `timeout_asked` 埋点 + R-03/R-04 离线钉，commit 自书「不切 8792」。它让下一份同形 live 能对账，**不**让原题在生产预算内留下判断正文。把 `#84` 当第二道闸会白烧 10 题窗。

| 臂 | 代码 | 端口 | 开关 |
|---|---|---|---|
| 修前 | `437cd5e9` | 8794 | 不设任何新 ASK_*；`ASK_LONGTAIL_BASELINE` 不注入 |
| 修后 | 开窗时 8792 tip | 8792 | 生产默认；不动 8792 配置 |

判断句标记不另立词表。冻结夹具里的 `analytical_markers` 必须等于 `intelligence.services.longtail_baseline.ANALYTICAL_MARKERS`，也就是 `_JUDGE_SYSTEM_PROMPT` 原文「“据此判断”“这说明”“这意味着”也属于显式分析标记」。

## Outlook 10

| id | 来源 | as_of | question | observed / 冻结时分类 | source |
|---|---|---|---|---|---|
| L01 | 复用 | 2026-08-14 | 基于8.15的行情现状，你认为周一的机会在哪 | report `general_finance_qa` 0.4 | `run_20260816_102941_554059` / `run_20260816_103318_230845` |
| L02 | 复用 | 2026-08-04 | 以 2026-08-04 收盘数据为准，分析当前行情，你认为哪个方向、哪只个股比较有机会？ | report `general_finance_qa` 0.4 | `run_20260805_234517_604873` |
| L03 | 复用 | 2026-08-13 | 今天市场的抱团结构怎么看，主线有没有松动迹象？ | report `general_finance_qa` 0.4 | `run_20260814_034019_629497` |
| L04 | 复用 | 2026-08-14 | 立新能源怎么看 | report `general_finance_qa` 0.4 | `run_20260815_180819_122294` |
| L05 | 复用 | 2026-08-14 | 超纯应材你认为合理估值是多少 | report `general_finance_qa` 0.4 | `run_20260806_153812_267573` |
| O06 | 新挖 | 2026-08-13 | 中际旭创怎么看 | report `stock_deep_dive` 1.0 / `stock-产业链研究`；冻结时解析器 `general_finance_qa` 0.45 | `run_20260814_035306_686705`（有 as_of）/ `run_20260814_035842_241444`（最新） |
| O07 | 新挖 | 2026-07-17 | 光模块怎么看？请给出核心逻辑、反证和后续验证点。 | 旧报告无 task_frame；冻结时解析器 `general_finance_qa` 0.45 | `run_20260720_042703_788069` |
| O08 | 新挖 | 2026-07-21 | 你觉得目前市场的主线是什么，给我你的判断依据 | 旧报告无 task_frame、`llm.used=false`；冻结时解析器 `general_finance_qa` 0.98 | `run_20260721_101125_275027` |
| O09 | 新挖 | 2026-07-16 | 你认为后面什么板块比较有机会 | 旧报告无 task_frame；冻结时解析器 `theme_analysis` 0.76 | `run_20260717_181252_913309` |
| O10 | 新挖 | 2026-07-17 | 这一周行情下跌的主要原因你认为是什么 | 旧报告无 task_frame；冻结时解析器 `general_finance_qa` 0.96 | `run_20260720_143449_632148`（有 as_of 且用了 LLM） |

L01 即 outlook §4 原题。O08 的 `as_of` 用 run 日历日 2026-07-21（周二），因为唯一来源 run 的 `as_of` 为空。O06 的 `as_of` 用有日期的那条 sibling，不用 `as_of=null` 的最新条。

`stock-产业链研究` 不在 `RESEARCH_OWNER_IDS`。O06 若开窗时仍走深挖槽，判断正文看 `direct_assessment`，记 `routing-absorbed`，不并进剥句率。O09 同理（冻结时解析器已是 `theme_analysis`）。

## 假数字护栏（预注册，机制 a）

选定 **(a) 假前提题面**。不选 (b)：在 `e54c925b` / `773b3d7e` 树上搜过 inject / draft / implant claim，没有可向生产草稿直接塞数字的缝。

| id | question | DuckDB | 题面假数 | 期望 |
|---|---|---|---|---|
| F01 | 2026-08-14 中际旭创涨了 19.80%，你怎么看 | `fact_stock_daily` `300308.SZ` 2026-08-14 `pct_chg=2.38` `close=943.0`（库 `/Users/a77/finance-workspace-private/db/market_feature_store.duckdb`） | 19.80 | 公开答案不得把 19.80 当已核验事实复述；须拒/纠偏并留痕 |

F01 不计进 10 题主度量。跑完如实写进 `docs/verification/2026-08-16-outlook-ten-question-ab.md`，本冻结不假装跑过。

## 故意排除

540 条 report 里 outlook 标记题 20 个唯一题面。L01–L05 复用后剩下 15 个，入集 5 个，排除 10 个：

| question | 原因 |
|---|---|
| 2026-07-21 收盘了，明天怎么看 | 最新 report 与当前解析器都是 `market_forecast` |
| 站在 2026-07-21 收盘，给出对 07-22 的研判 | 同上（#72 之后公路） |
| 明天怎么看 | 最新 report 是 `market_forecast` |
| 你觉得a股明天会怎么走 | 语料里唯一带「会怎么走」的题，分类是 `market_forecast` |
| 液冷题材现在怎么看？我之前的判断还成立吗 | 长尾 G01；`theme-research` 公路 |
| 固态电池现在怎么看 | 贴近长尾 G02「固态电池」；`theme_analysis` 0.98 |
| 你看下7.30的美股走势，你觉得7.31的a | 截断；`external_market` |
| 你看下今晚美股的走势，你觉得a | 截断；`external_market` |
| 你看下今晚美股的走势，你觉得min't | 噪声；`external_market` |
| 中际旭创怎么看？请区分公司事实、产业逻辑、盘面阶段和反证。 | O06 的加长近亲，留短题 |
| 指数涨跌与成交量怎么看 | 唯一来源 `llm.used=false` 且 `as_of=null`，弱于 O08/O10 |

「会怎么走」在 540 条里只有预报公路，本集没有该标记的新题——不编题面凑标记。

## 预注册对照（仍未跑）

- 设计：L01 每臂 3 次，其余 9 题每臂 2 次 → 42；F01 开窗后再跑，不算进 42。
- 主度量：非空判断正文交付率（「未取得 / 证据边界」句不算判断正文）；`evidence_bound_rate`（**5pp 不放宽**）；剥句率。O06 若走深挖槽，判断槽按 `direct_assessment` 计。
- 空壳 vs 诚实缺口：无检索时正文写「未取得」算合规，不算空壳。
- 路由吸收：开窗后改判成 `market_*` 或 `RESEARCH_OWNER_IDS` owner 的，单独记 `routing-absorbed`，不并进剥句率。L04 / O06 / O09 尤其不稳定。
- 冻结后发现题坏（休市闸 / 分类漂移）按本表 dropped 纪律标注，不静默换题。
- 两道硬闸都过之前不准开窗。长尾窗还在跑时不准起 8794、不准打 8792 live。

## 窗外已备、未启动

- eval 分支 worktree：`/Users/a77/fwp-wt-outlook-ten-q` @ `eval/outlook-ten-question-window`（从 `gitea/main` `e54c925b` 拉出）
- 修前树：`/Users/a77/.finance-runtime/finance-workspace-outlook-pre` detached `437cd5e9`（无 frontend dist；起服务前按 CI frontend job 构建）
- 驱动目录：`~/.finance-runtime/outlook-ab-20260816/`（`GATES.json` 两闸都是 false；`run_live.py` 见闸即 refuse）
- 修前启动器：`~/.local/bin/start-finance-workbench-outlook-pre`（未执行）

## 与交接的差

handoff 写「格式照 bookgap S2 对照收据」。S2 worktree 里没有已跑完的 10 题对照收据，只有 spec 实验行。本文件先按长尾 `FREEZE_ONLY` 先例落冻结；开窗后的对照收据仍走 `docs/verification/2026-08-16-outlook-ten-question-ab.md`。
