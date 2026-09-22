# 2026-09-22 自适应研究回路 · 传输层绝对截止复核（工单 #72）

接手方独立复核，不复用作者收据。被测提交 `aa0509d61fb063be6fd2d2ac3ddc15732e6fd16e`（分支 `feat/adaptive-research-loop`），
隔离树 `~/fwp-wt-adaptive-deadline-0922`（`git worktree add --detach … aa0509d61`，首尾 `dirty=false`），
解释器 `~/finance-workspace-private/.venv-workbench/bin/python`，独占 `basetemp`，开跑时 load 5.18。
原始日志根 `~/.finance-runtime/adaptive-deadline-0922/`。

## 目标 1：严格探针（13 场景）

`PYTHONPATH=. python scripts/review_probes/diagnose_llm_timeout.py --assert-deadline --output strict-deadline.json`
→ **exit 0，`deadline_violations: []`**，本目录 `strict-deadline.json`（容差 0.2 s，`source_before == source_after`）。

| 场景 | 获批 | 实测墙钟 | 台账 status/reason |
|---|---:|---:|---|
| fast | 0.8 | 0.109 | success |
| header_delay | 0.8 | 0.805 | failed/timeout |
| body_stall | 0.8 | 0.802 | failed/timeout |
| headers_then_body | 0.8 | 0.808 | failed/timeout |
| body_trickle | 0.8 | 0.808 | failed/timeout |
| tools_stream_trickle | 0.8 | 0.805 | failed/timeout |
| tools_stream_partial_line | 0.8 | 0.806 | failed/timeout |
| synthesis_stream_trickle | 1.2 | 1.214 | failed/timeout |
| synthesis_stream_partial_line | 1.2 | 1.211 | failed/timeout |
| zero_deadline | 0.0 | 0.000 | 无请求、无预占 |
| judge_window_stalls | 0.8 | 0.807 | failed/timeout |
| judge_late_report | 0.8 | 0.812 | failed/timeout |
| judge_root_expired | 0.0 | 0.000 | 无请求 |

作者在 `a9ba35159` 上测到的 7 个越窗（+0.25 ～ +3.16 s）在 `aa0509d61` 上全部归零；接手方独立复现，与作者
`final-strict-deadline.json` 结论一致。非流式场景 `content_present=False`，流式场景 `emitted_chars>0` 但正文未被采纳。

## 目标 2：判官迟到回包

`judge_late_report`（批 0.8 s、对端 ~2.9 s 才吐完）：`report_received=False`、`unavailable=True`、
台账唯一一行 `status=failed / reason=timeout`、`request_count == reserved_count == len(records) == 1`、
`remaining_root_seconds=8.79`（根预算按实际消耗扣，不再按「对方守约」记）。
常规回归 `test_real_late_judge_report_is_rejected_at_the_transport_boundary` 守这一条。

## 验收「阳性对照」：变异存活 → 补用例 → 杀死

工单要求：把 `_open_deadline_http_response` 的 `deadline` 改为不传，至少一条**常规** pytest 用例红。

| 步骤 | 命令 / 改动 | 结果 |
|---|---|---|
| 变异 | `llm_refine.py:222` `deadline=deadline` → `deadline=None`（`git diff` 1 行） | — |
| 定向套件（作者版 25 条） | `pytest intelligence/tests/test_llm_timeout_diagnostic.py` | **25 passed，变异存活** |
| 广域（另 13 个引用传输层的测试文件） | `pytest conformance_transport test_ask_call_provenance … test_served_model_receipt` | **351 passed，变异存活** |
| 补用例 | 新增 `test_refine_wrapper_forwards_the_shared_deadline_to_the_transport`：单发片 10 s、共享截止 0.5 s、对端 ~2.9 s 滴流，断言 `LLMDeadlineExceeded` 且墙钟 < 2 s | 变异下 **1 failed（DID NOT RAISE）** |
| 还原 | `git checkout -- intelligence/services/llm_refine.py`，sha256 `ff587c50…a424` 与 `HEAD` 一致 | 26 passed，ruff 通过 |

为什么此前无人守：探针与 `test_call_timeout_never_outlives_the_shared_research_deadline` 里「单发片」与「共享截止」
两个值要么相等、要么直接驱动传输层绕过了包装函数，所以丢掉包装函数里的 `deadline=` 转发对它们不可见。
两个入参在所有夹具里同值时，删掉其中一个的变异一定存活——阳性对照必须让这两个值分开。
（同族原则：`~/agent-memory` 的 `two-defence-layers-need-two-separate-assertions`。）

变异全程 `PYTHONDONTWRITEBYTECODE=1`，日志 `mut-broad.log` / `mut-newtest.log` / `post-restore-targeted.log`，
sha256 见 `llm_refine.head.sha256` / `llm_refine.restored.sha256`，结构化记录见本目录 `mutation-record.json`。

## 工单步骤 1 的「2 个未提交路径」处置

工单以 22:20 的分支状态为起点，当时树上 2 个未提交路径。接手时（23:39）作者树 `~/finance-worktrees/adaptive-research-loop`
`git status --short` 为空；`git show --stat aa0509d61`（22:35）恰好只含 `docs/handoffs/2026-09-22-adaptive-deadline-transport.md`
与 `docs/handoffs/inflight/feat-adaptive-research-loop.md` 两个文件。判定：那 2 个路径已由作者以 `aa0509d61` 提交，无需另行落盘。

## 非目标（按工单原样未动）

未改 T900 / 75 / 150 预算；未开 `derived_calculation`；未碰数字门单位错位（issue #852）；未跑真实模型；
未给 `--assert-deadline` 探针加容忍；未动生产 8792。

## 合流尖四叶门禁

`c582d6755` 之上 `--no-ff` 合入 `gitea/main@f24a61a8a` 得 `013eb5c4a`（merge-tree 预检 0 冲突），隔离树 `checkout --detach 013eb5c4a`
跑一次性执行器 `~/.finance-runtime/adaptive-deadline-0922/run_gate.py`（三叶并行、不 fail-fast、每叶记首尾身份与日志 sha256），
收据根 `~/.finance-runtime/adaptive-deadline-0922/gate-013eb5c4a/`，`summary.json` 是索引，九项 exit 0、每叶首尾身份一致：

| 叶 | 读数 | 收据 |
|---|---|---|
| ruff | exit 0 | `ruff.run.json` |
| pytest 全量 | **12879 passed / 85 skipped / 2 xfailed**，exit 0，2030 s（load 9.3 → 16.6，机器上另有两位 agent 的全量 pytest） | `pytest-full.pytest-receipt.json`（`check_test_receipt.py --expect-revision 013eb5c4a…` ✅ 可采信）、`pytest-full.xml` |
| 前端六步 | install / lint / typecheck / test（110 passed，8 文件）/ build / E2E（34 passed / 2 skipped）全 exit 0，端口 19971/19974 | `frontend/frontend.json` |
| registry ×4 + ledger-spec-crosswalk | 五项 exit 0 | `registry-*.run.json`、`ledger-crosswalk.run.json` |
| 严格探针（合流尖） | exit 0，`deadline_violations: []` | `strict-deadline.json`（副本：本目录 `strict-deadline-013eb5c4a.json`） |

PR head 若在 `013eb5c4a` 之上，只允许 docs 提交（`git diff --stat 013eb5c4a..<head>` 应只有 `docs/`）。

## 附加变异（非验收项）：`is_cancelled=` 转发也无人守

同法把包装函数的 `is_cancelled=is_cancelled` 改为 `is_cancelled=None`，跑 `test_llm_timeout_diagnostic.py`、`test_llm_refine_tool_stream.py`、
`test_conversation_orchestrator.py -k cancel`：**15 passed，变异存活**（`mut-cancel2.log`；还原后 sha256 与 HEAD 一致）。
原因同上：`llm_refine` 读流循环每行自查 `is_cancelled()`，现有取消测试都在「有行到达」时取消；传输层 0.05 s 轮询取消只在**停顿期**才有区别。
本单不补代码（不在验收项、会让门禁过的代码尖再漂一层），配方留给下一刀：`body_stall` 端点（1 字节后停 1.6 s）+ 0.3 s 后翻真的 `is_cancelled`，
片 / 截止都给 10 s，经 `_open_deadline_http_response` 断言 `LLMStreamCancelled` 且墙钟 < 1 s；变异下应读到停顿结束才返回（DID NOT RAISE）。

## 交 #76（L6 自适应回路真实改稿复核）条件卡

- **前置**：严格探针 exit 0 已在 `aa0509d61` 与合流尖 `013eb5c4a` 各独立跑一次，均 0 越窗；`judge_late_report` 类迟到回包由常规回归守为 `failed/timeout`，零采纳。
- **固定 SHA**：按 #76 表原文以「#72 合入后的 `gitea/main` SHA」为准；合入前候选 = 本 PR head，被门禁的代码尖 `013eb5c4a`（其上只允许 docs 提交）。开跑前冻结代码与数据，`protocol.json` 记 revision、`dirty=false`、各 canonical `fact_*` 的 `max(trade_date)`。
- **三题冒烟原题**（逐字，来源 `~/.finance-runtime/adaptive-live-smoke-20260921{,-q2,-q3}/probe/protocol.json`）：
  1. 寒武纪(688256.SH)这轮行情，给我一组可证伪的跟踪条件：需要哪些指标达到什么数值才算逻辑兑现，出现哪些数值算证伪。每个数值请标明它的来源和对应日期。（全工具）
  2. 只用本地已有资料，不联网：东阳光(600673.SH)9月以来的量价表现如何，与所属板块相比强弱如何？给出具体数值、日期和数据来源；本地没有的部分单独列出，不要补。（`local_only` 四只读能力）
  3. 固态电池题材这轮行情发酵到哪一步了？给我一组可证伪的跟踪条件，每个数值标明来源和日期。（theme_track，全工具）
- **预算（不改）**：环境根 T900 s；Episode 研究额度 600 s；单发帽 75 s；修订额度 30 s；判官每次核验共享窗 150 s；不开 `derived_calculation`。
- **模型与入口**：沿用 `docs/handoffs/2026-09-22-adaptive-absence-live.md` 协议——写手 `kimi-k3`（隔离旁车 8797、密钥内存传递、`remember=false`），独立判官 `glm-5.3-flash`；单臂 `off`，每题首发 1 次、重发 0；复用 `scripts/compare_adaptive_research.py` 的 POST 会话/消息入口，隔离 users / Episode / 待重核索引；不碰生产 8792。
- **判定项（#76 L6 原文）**：改稿轮 ≥ 1；改后**有证据的**数值条件句零误删（单位错位属 issue #852 那张单，出现即记 `BLOCKED_BY_852`，不改判、不顺手修）；trace 里迟到判官回包必须是 `failed/timeout`，出现 `success` 即 L6 不过。
- **必须写进协议的代价**：每次 HTTP 调用多一次子进程启动（空闲 ~0.15 s、高负载 >0.35 s，计入调用预算）。对 75/150 s 窗口占比 1–3%，不影响判定；但**机器 load > 20 时不要开跑**（作者实测 load 40 下亚秒窗口提前失败）。批前先探网关 `chat/completions`。
- **不刷绿**：`adaptive-absence-live` 记的东阳光内容错（板块累计涨跌幅、强弱方向反转）依然成立，本单一个字没动内容层；#76 复跑第 2 题是新预注册样本，不覆盖旧原件。

## 交 #75（第二方 Spec + Quality）需求

- **候选**：PR 号与 head 见 PR / 交接；被门禁的代码尖 `013eb5c4a`；`git diff --stat 013eb5c4a..<head>` 应只有 `docs/`。
- **候选检出路径（绝对）**：`/Users/a77/fwp-wt-adaptive-deadline-0922`（隔离树，只读引用；审查者应自建树）。
- **证据目录**：本单 `~/.finance-runtime/adaptive-deadline-0922/`（复核、变异、四叶 `gate-013eb5c4a/`）；作者侧 `~/.finance-runtime/adaptive-advance-20260922/`；上一轮审计 `~/.finance-runtime/adaptive-closeout-20260922/`。
- **主张清单来源**：PR 描述「主张清单」节（Spec 轴输入）。
- **Quality 轴建议探针**：复跑本目录 `mutation-record.json` 的变异；对 `llm_http_transport.urlopen` 复跑作者 M1（父侧截止关）/ M2（子侧硬停关）/ M4（共享截止 `min` 忽略）确认仍被杀。
- **本单未覆盖、请审查者留意**：`_open_deadline_http_response` 的 `is_cancelled=` 转发未做阳性对照；四处调用点的 `timeout` 片是否都经 `Deadline.slice()` 派生未逐点核。
